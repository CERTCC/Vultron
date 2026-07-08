#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Unit tests for embargo lifecycle and state-machine nodes (lifecycle.py)."""

from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.nodes.lifecycle import (
    ValidateEmbargoRevisionStateNode,
)
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

from test.core.behaviors.embargo.nodes.conftest import make_case_and_embargo

ACTOR_ID = "https://example.org/actors/vendor"
CASE_MANAGER_ACTOR = "https://example.org/actors/case-manager"


def _make_case_with_manager(
    suffix: str,
    em_state: EM = EM.ACTIVE,
) -> tuple[VulnerabilityCase, CaseParticipant, SqliteDataLayer]:
    """Return a populated DataLayer with a case + CASE_MANAGER participant."""
    dl = SqliteDataLayer("sqlite:///:memory:")
    case, _embargo = make_case_and_embargo(suffix, em_state=em_state)

    cm_participant = CaseParticipant(
        id_=f"{case.id_}/participants/cm",
        attributed_to=CASE_MANAGER_ACTOR,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.case_participants.append(cm_participant.id_)
    case.actor_participant_index[CASE_MANAGER_ACTOR] = cm_participant.id_

    dl.create(case)
    dl.create(cm_participant)
    return case, cm_participant, dl


def _make_factory() -> MagicMock:
    factory = MagicMock()
    factory.terminate_embargo.return_value = (
        "https://example.org/activities/act1",
        {},
    )
    return factory


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()


# ---------------------------------------------------------------------------
# terminate_embargo_bt — shared factory (BT-19-001, BT-19-002)
# ---------------------------------------------------------------------------


class TestTerminateEmbargoBT:
    """Tests for the shared terminate_embargo_bt factory (BT-19-001)."""

    def test_terminates_active_embargo(self):
        """Shared BT transitions ACTIVE → EXITED and queues the activity."""
        case, _, dl = _make_case_with_manager("teb1", em_state=EM.ACTIVE)
        factory = _make_factory()
        result_out: dict = {}

        def builder(case_manager_id: str) -> list[str]:
            aid, _ = factory.terminate_embargo(
                embargo_id="https://example.org/cases/case_teb1/embargo_events/e1",
                case_id=case.id_,
                actor=ACTOR_ID,
                to=[case_manager_id],
            )
            return [aid]

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        tree = terminate_embargo_bt(
            case_id=case.id_, result_out=result_out, activity_builder=builder
        )
        result = bridge.execute_with_setup(tree, actor_id=ACTOR_ID)

        assert result.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em_state == EM.EXITED
        assert updated.active_embargo is None
        factory.terminate_embargo.assert_called_once()

    def test_terminates_revise_embargo(self):
        """Shared BT transitions REVISE → EXITED."""
        case, _, dl = _make_case_with_manager("teb2", em_state=EM.REVISE)
        factory = _make_factory()
        result_out: dict = {}

        def builder(case_manager_id: str) -> list[str]:
            aid, _ = factory.terminate_embargo(
                embargo_id="https://example.org/cases/case_teb2/embargo_events/e1",
                case_id=case.id_,
                actor=ACTOR_ID,
                to=[case_manager_id],
            )
            return [aid]

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        tree = terminate_embargo_bt(
            case_id=case.id_, result_out=result_out, activity_builder=builder
        )
        result = bridge.execute_with_setup(tree, actor_id=ACTOR_ID)

        assert result.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em_state == EM.EXITED

    def test_missing_case_manager_returns_failure_before_state_change(self):
        """AC-5: Missing CASE_MANAGER → FAILURE; EM state and active_embargo unchanged."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, embargo = make_case_and_embargo("teb3", em_state=EM.ACTIVE)
        dl.create(case)  # no CASE_MANAGER participant

        factory = _make_factory()
        result_out: dict = {}

        def builder(case_manager_id: str) -> list[str]:
            aid, _ = factory.terminate_embargo(
                embargo_id=embargo.id_,
                case_id=case.id_,
                actor=ACTOR_ID,
                to=[case_manager_id],
            )
            return [aid]

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        tree = terminate_embargo_bt(
            case_id=case.id_, result_out=result_out, activity_builder=builder
        )
        result = bridge.execute_with_setup(tree, actor_id=ACTOR_ID)

        # BT fails at routing guard — no state mutation occurs (BT-19-001).
        assert result.status == py_trees.common.Status.FAILURE
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em_state == EM.ACTIVE  # unchanged
        assert updated.active_embargo is not None  # unchanged
        factory.terminate_embargo.assert_not_called()

    def test_no_active_embargo_returns_failure(self):
        """BT returns FAILURE when the case has no active embargo."""
        case, _, dl = _make_case_with_manager("teb4", em_state=EM.NONE)
        case_obj = cast(VulnerabilityCase, dl.read(case.id_))
        case_obj.active_embargo = None
        dl.save(case_obj)

        factory = _make_factory()
        result_out: dict = {}

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        tree = terminate_embargo_bt(
            case_id=case.id_,
            result_out=result_out,
            activity_builder=lambda _: [],
        )
        result = bridge.execute_with_setup(tree, actor_id=ACTOR_ID)

        assert result.status == py_trees.common.Status.FAILURE
        factory.terminate_embargo.assert_not_called()

    def test_resets_participant_pec_state(self):
        """Shared BT resets participant embargo_consent_state to NO_EMBARGO."""
        case, _, dl = _make_case_with_manager("teb5", em_state=EM.ACTIVE)
        participant = CaseParticipant(
            id_=f"{case.id_}/participants/p1",
            attributed_to="https://example.org/users/vendor",
        )
        participant.embargo_consent_state = PEC.SIGNATORY.value
        case_obj = cast(VulnerabilityCase, dl.read(case.id_))
        case_obj.case_participants.append(participant.id_)
        dl.save(case_obj)
        dl.create(participant)

        factory = _make_factory()
        result_out: dict = {}

        def builder(case_manager_id: str) -> list[str]:
            aid, _ = factory.terminate_embargo(
                embargo_id="https://example.org/cases/case_teb5/embargo_events/e1",
                case_id=case.id_,
                actor=ACTOR_ID,
                to=[case_manager_id],
            )
            return [aid]

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        tree = terminate_embargo_bt(
            case_id=case.id_, result_out=result_out, activity_builder=builder
        )
        result = bridge.execute_with_setup(tree, actor_id=ACTOR_ID)

        assert result.status == py_trees.common.Status.SUCCESS
        updated_p = cast(CaseParticipant, dl.read(participant.id_))
        assert updated_p.embargo_consent_state == PEC.NO_EMBARGO.value

    def test_cascade_path_no_builder_returns_failure_when_no_factory(self):
        """Without activity_builder, FAILURE when no trigger_activity_factory set.

        This is the cascade path used by PublicDisclosureBranchNode (BT-14-001).
        """
        case, _, dl = _make_case_with_manager("teb6", em_state=EM.ACTIVE)
        result_out: dict = {}

        # No trigger_activity in BTBridge → factory is None on blackboard
        bridge = BTBridge(datalayer=dl)
        tree = terminate_embargo_bt(
            case_id=case.id_,
            result_out=result_out,
        )
        result = bridge.execute_with_setup(tree, actor_id=ACTOR_ID)

        assert result.status == py_trees.common.Status.FAILURE

    def test_cascade_path_terminates_when_factory_present(self):
        """Without activity_builder, SUCCESS when factory resolves from blackboard."""
        case, _, dl = _make_case_with_manager("teb7", em_state=EM.ACTIVE)
        factory = _make_factory()
        result_out: dict = {}

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        tree = terminate_embargo_bt(
            case_id=case.id_,
            result_out=result_out,
        )
        result = bridge.execute_with_setup(tree, actor_id=ACTOR_ID)

        assert result.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em_state == EM.EXITED
        factory.terminate_embargo.assert_called_once()
        outbox = dl.outbox_list_for_actor(ACTOR_ID)
        assert "https://example.org/activities/act1" in outbox

    def test_cascade_path_missing_case_manager_failure_before_state_change(
        self,
    ):
        """AC-5 (cascade path): Missing CASE_MANAGER → FAILURE; no state mutation."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("teb8", em_state=EM.ACTIVE)
        dl.create(case)  # no CASE_MANAGER participant

        factory = _make_factory()
        result_out: dict = {}

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        tree = terminate_embargo_bt(
            case_id=case.id_,
            result_out=result_out,
        )
        result = bridge.execute_with_setup(tree, actor_id=ACTOR_ID)

        assert result.status == py_trees.common.Status.FAILURE
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em_state == EM.ACTIVE  # unchanged
        assert updated.active_embargo is not None  # unchanged
        factory.terminate_embargo.assert_not_called()


# ---------------------------------------------------------------------------
# ValidateEmbargoRevisionStateNode
# ---------------------------------------------------------------------------


class TestValidateEmbargoRevisionStateNode:
    """Tests for ValidateEmbargoRevisionStateNode."""

    def _setup_blackboard(self, dl: SqliteDataLayer) -> None:
        py_trees.blackboard.Blackboard.enable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()
        blackboard = py_trees.blackboard.Client(name="test-ver")
        for key in ("datalayer", "actor_id"):
            blackboard.register_key(
                key=key, access=py_trees.common.Access.WRITE
            )
        blackboard.datalayer = dl
        blackboard.actor_id = "https://example.org/actors/alice"

    def _run_node(
        self, dl: SqliteDataLayer, case_id: str
    ) -> tuple[py_trees.common.Status, dict]:
        result_out: dict = {}
        self._setup_blackboard(dl)

        node = ValidateEmbargoRevisionStateNode(
            case_id=case_id, result_out=result_out
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()
        return node.status, result_out

    def test_returns_success_when_em_state_is_active(self):
        """SUCCESS when case EM state is ACTIVE."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("rev1", em_state=EM.ACTIVE)
        dl.create(case)

        status, result_out = self._run_node(dl, case.id_)

        assert status == py_trees.common.Status.SUCCESS
        assert "error" not in result_out

    def test_returns_success_when_em_state_is_revise(self):
        """SUCCESS when case EM state is REVISE."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("rev2", em_state=EM.REVISE)
        dl.create(case)

        status, result_out = self._run_node(dl, case.id_)

        assert status == py_trees.common.Status.SUCCESS
        assert "error" not in result_out

    def test_returns_failure_when_em_state_is_none(self):
        """FAILURE when case EM state is NONE (no active embargo)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("rev3", em_state=EM.NONE)
        case.active_embargo = None
        dl.create(case)

        status, result_out = self._run_node(dl, case.id_)

        assert status == py_trees.common.Status.FAILURE
        assert "error" in result_out

    def test_returns_failure_when_em_state_is_proposed(self):
        """FAILURE when case EM state is PROPOSED (initial proposal, not revision)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("rev4", em_state=EM.PROPOSED)
        dl.create(case)

        status, result_out = self._run_node(dl, case.id_)

        assert status == py_trees.common.Status.FAILURE
        assert "error" in result_out

    def test_returns_failure_when_em_state_is_exited(self):
        """FAILURE when case EM state is EXITED."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("rev5", em_state=EM.EXITED)
        dl.create(case)

        status, result_out = self._run_node(dl, case.id_)

        assert status == py_trees.common.Status.FAILURE
        assert "error" in result_out

    def test_error_is_invalid_state_transition(self):
        """Error in result_out is VultronInvalidStateTransitionError for bad state."""
        from vultron.errors import VultronInvalidStateTransitionError

        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("rev6", em_state=EM.NONE)
        case.active_embargo = None
        dl.create(case)

        _, result_out = self._run_node(dl, case.id_)

        assert isinstance(
            result_out["error"], VultronInvalidStateTransitionError
        )

    def test_returns_failure_when_case_not_found(self):
        """FAILURE when the case ID does not exist in the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        self._setup_blackboard(dl)

        status, result_out = self._run_node(
            dl, "https://example.org/cases/nonexistent"
        )

        assert status == py_trees.common.Status.FAILURE
        assert "error" in result_out
