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

from test.core.behaviors.embargo.nodes.conftest import (
    OTHER_PARTICIPANT_ACTOR,
    make_case_and_embargo,
    make_case_with_manager,
)
from test.support.embargo_register import propose
from test.support.ledger import committed_event_types
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.nodes import EMBARGO_TEARDOWN_EVENT_TYPE
from vultron.core.behaviors.embargo.nodes.lifecycle import (
    ProposeEmbargoLifecycleNode,
    SetEmbargoActiveNode,
    ValidateEmbargoRevisionStateNode,
)
from vultron.core.behaviors.embargo.trigger_tree import (
    ASSERTED_ACTIVITY_KEY,
    terminate_embargo_bt,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

ACTOR_ID = "https://example.org/actors/vendor"
CASE_MANAGER_ACTOR = "https://example.org/actors/case-manager"


def _make_case_with_manager(
    suffix: str,
    em_state: EM = EM.ACTIVE,
) -> tuple[VulnerabilityCase, as_CaseParticipant, SqliteDataLayer]:
    """Return a populated DataLayer with a case + CASE_MANAGER participant."""
    dl = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=ACTOR_ID,
    )
    case, _ = make_case_and_embargo(suffix, em_state=em_state)

    cm_participant = as_CaseParticipant(
        id_=f"{case.id_}/participants/cm",
        attributed_to=CASE_MANAGER_ACTOR,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.case_participants.append(cm_participant.id_)
    case.actor_participant_index[CASE_MANAGER_ACTOR] = cm_participant.id_

    dl.create(case)
    dl.create(cm_participant)
    return case, cm_participant, dl


def _embargo_id(case: VulnerabilityCase) -> str:
    return f"{case.id_}/embargo_events/e1"


def _store_active_embargo(
    dl: SqliteDataLayer, case: VulnerabilityCase
) -> None:
    """Store the embargo the case points at, which the factory renders."""
    dl.create(
        as_EmbargoEvent(
            id_=_embargo_id(case),
            context=case.id_,
            end_time=days_from_now_utc(45),
        )
    )


def _make_factory() -> MagicMock:
    factory = MagicMock()
    factory.terminate_embargo.return_value = (
        "https://example.org/activities/act1",
        {},
    )
    return factory


# ---------------------------------------------------------------------------
# terminate_embargo_bt — shared factory (BT-19-001, BT-19-002)
# ---------------------------------------------------------------------------


class TestTerminateEmbargoBT:
    """Tests for the shared terminate_embargo_bt factory (BT-19-001).

    A trigger writes shared EM state only as the CASE_MANAGER (EP-09-008), so
    the tests that expect a teardown run as the role holder, in its store;
    a non-manager's run asks and writes nothing.
    """

    @staticmethod
    def _run_as_manager(
        suffix: str, em_state: EM = EM.ACTIVE, *, use_builder: bool = True
    ) -> tuple[VulnerabilityCase, SqliteDataLayer, MagicMock]:
        case, _cm, dl = make_case_with_manager(suffix, em_state=em_state)
        _store_active_embargo(dl, case)
        factory = MagicMock(wraps=TriggerActivityAdapter(dl))

        def builder(to: list[str] | None) -> tuple[str, str]:
            return cast(
                tuple[str, str],
                factory.terminate_embargo(
                    embargo_id=_embargo_id(case),
                    case_id=case.id_,
                    actor=CASE_MANAGER_ACTOR,
                    to=to,
                ),
            )

        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=factory,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        tree = terminate_embargo_bt(
            case_id=case.id_,
            result_out={},
            reason=TerminationReason.EARLY,
            activity_builder=builder if use_builder else None,
        )
        result = bridge.execute_with_setup(tree, actor_id=CASE_MANAGER_ACTOR)
        assert result.status == py_trees.common.Status.SUCCESS
        return case, dl, factory

    @pytest.mark.spec("EMB-07-001")
    @pytest.mark.spec("EP-09-008")
    def test_terminates_active_embargo(self):
        """As the CASE_MANAGER: ACTIVE → EXITED, committed as an entry."""
        case, dl, factory = self._run_as_manager("teb1", em_state=EM.ACTIVE)

        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.em_state == EM.EXITED
        assert updated.active_embargo is None
        factory.terminate_embargo.assert_called_once()
        assert EMBARGO_TEARDOWN_EVENT_TYPE in committed_event_types(
            dl, case.id_
        )

    @pytest.mark.spec("EMB-07-002")
    def test_terminates_revise_embargo(self):
        """As the CASE_MANAGER: REVISE → EXITED."""
        case, dl, _factory = self._run_as_manager("teb2", em_state=EM.REVISE)

        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.em_state == EM.EXITED

    @pytest.mark.spec("EMB-19-001")
    @pytest.mark.parametrize("use_builder", [True, False])
    def test_manager_teardown_is_addressed_to_the_others_only(
        self, use_builder: bool
    ):
        """The manager's ``Remove`` reaches every other participant and never
        the manager itself (CLP-10-001, #4112) — trigger and cascade alike."""
        _case, dl, _factory = self._run_as_manager(
            f"teb9{int(use_builder)}", use_builder=use_builder
        )

        removes = [
            cast(VultronActivity, dl.read(i))
            for i in dl.outbox_list()
            if cast(VultronActivity, dl.read(i)).type_ == "Remove"
        ]
        assert [r.to for r in removes] == [[OTHER_PARTICIPANT_ACTOR]]
        assert not any(
            CASE_MANAGER_ACTOR in (r.to or []) + (r.cc or []) for r in removes
        )

    @pytest.mark.spec("EP-09-008")
    def test_non_manager_asks_and_writes_nothing(self):
        """A non-manager's terminate queues the ``Remove`` to the CASE_MANAGER
        and leaves the embargo in force (PCR-08-001, #4112)."""
        case, _cm, manager_dl = make_case_with_manager("teb10")
        # A BT's store follows its executing actor (BT-05-005): the
        # participant runs in its own replica of the case.
        dl = SqliteDataLayer(
            "sqlite:///:memory:", actor_id=OTHER_PARTICIPANT_ACTOR
        )
        for obj_id in (case.id_, *case.actor_participant_index.values()):
            obj = manager_dl.read(obj_id)
            assert obj is not None
            dl.create(obj)
        _store_active_embargo(dl, case)
        factory = TriggerActivityAdapter(dl)
        result_out: dict = {}

        def builder(to: list[str] | None) -> tuple[str, str]:
            return cast(
                tuple[str, str],
                factory.terminate_embargo(
                    embargo_id=_embargo_id(case),
                    case_id=case.id_,
                    actor=OTHER_PARTICIPANT_ACTOR,
                    to=to,
                ),
            )

        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=factory,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        tree = terminate_embargo_bt(
            case_id=case.id_,
            result_out=result_out,
            reason=TerminationReason.EARLY,
            activity_builder=builder,
        )
        result = bridge.execute_with_setup(
            tree, actor_id=OTHER_PARTICIPANT_ACTOR
        )

        assert result.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.em_state == EM.ACTIVE
        assert updated.active_embargo is not None
        queued = [cast(VultronActivity, dl.read(i)) for i in dl.outbox_list()]
        assert [(a.type_, a.to) for a in queued] == [
            ("Remove", [CASE_MANAGER_ACTOR])
        ]
        assert result_out[ASSERTED_ACTIVITY_KEY] == queued[0].id_
        assert committed_event_types(dl, case.id_) == []

    def test_missing_case_manager_returns_failure_before_state_change(self):
        """AC-5: Missing CASE_MANAGER → FAILURE; EM state and active_embargo unchanged."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, embargo = make_case_and_embargo("teb3", em_state=EM.ACTIVE)
        dl.create(case)  # no CASE_MANAGER participant

        factory = _make_factory()
        result_out: dict = {}

        def builder(to: list[str] | None) -> tuple[str, str]:
            return cast(
                tuple[str, str],
                factory.terminate_embargo(
                    embargo_id=embargo.id_,
                    case_id=case.id_,
                    actor=ACTOR_ID,
                    to=to,
                ),
            )

        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=factory,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        tree = terminate_embargo_bt(
            case_id=case.id_,
            result_out=result_out,
            reason=TerminationReason.EARLY,
            activity_builder=builder,
        )
        result = bridge.execute_with_setup(tree, actor_id=ACTOR_ID)

        # BT fails at routing guard — no state mutation occurs (BT-19-001).
        assert result.status == py_trees.common.Status.FAILURE
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.em_state == EM.ACTIVE  # unchanged
        assert updated.active_embargo is not None  # unchanged
        factory.terminate_embargo.assert_not_called()

    def test_no_active_embargo_returns_failure(self):
        """BT returns FAILURE when the case has no active embargo."""
        case, _, dl = _make_case_with_manager("teb4", em_state=EM.NONE)

        factory = _make_factory()
        result_out: dict = {}

        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=factory,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        tree = terminate_embargo_bt(
            case_id=case.id_,
            result_out=result_out,
            reason=TerminationReason.EARLY,
            activity_builder=lambda _to: ("", ""),
        )
        result = bridge.execute_with_setup(tree, actor_id=ACTOR_ID)

        assert result.status == py_trees.common.Status.FAILURE
        factory.terminate_embargo.assert_not_called()

    @pytest.mark.spec("EMB-13-001")
    def test_leaves_consent_rows_untouched_and_nobody_a_signatory(self):
        """Termination writes no consent; with no active embargo nobody signs."""
        case, dl, _factory = self._run_as_manager("teb5", em_state=EM.ACTIVE)

        updated_case = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated_case.active_embargo_id is None
        embargo_id = _embargo_id(case)
        for participant_id in case.actor_participant_index.values():
            updated_p = cast(as_CaseParticipant, dl.read(participant_id))
            assert updated_p.consent_for(embargo_id) is (
                EmbargoConsentState.ACCEPTED
            )
            assert not updated_p.is_signatory(updated_case.active_embargo_id)

    def test_cascade_path_no_builder_returns_failure_when_no_factory(self):
        """Without activity_builder, FAILURE when no trigger_activity_factory set.

        This is the cascade path used by ThreatTerminationBranchNode (BT-14-001).
        """
        case, _, dl = _make_case_with_manager("teb6", em_state=EM.ACTIVE)
        result_out: dict = {}

        # No trigger_activity in BTBridge → factory is None on blackboard
        bridge = BTBridge(
            datalayer=dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        tree = terminate_embargo_bt(
            case_id=case.id_,
            result_out=result_out,
            reason=TerminationReason.EARLY,
        )
        result = bridge.execute_with_setup(tree, actor_id=ACTOR_ID)

        assert result.status == py_trees.common.Status.FAILURE

    def test_cascade_path_terminates_when_factory_present(self):
        """Without activity_builder, SUCCESS when factory resolves from blackboard."""
        case, dl, factory = self._run_as_manager("teb7", use_builder=False)

        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.em_state == EM.EXITED
        factory.terminate_embargo.assert_called_once()
        assert EMBARGO_TEARDOWN_EVENT_TYPE in committed_event_types(
            dl, case.id_
        )

    def test_cascade_path_missing_case_manager_failure_before_state_change(
        self,
    ):
        """AC-5 (cascade path): Missing CASE_MANAGER → FAILURE; no state mutation."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, _ = make_case_and_embargo("teb8", em_state=EM.ACTIVE)
        dl.create(case)  # no CASE_MANAGER participant

        factory = _make_factory()
        result_out: dict = {}

        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=factory,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        tree = terminate_embargo_bt(
            case_id=case.id_,
            result_out=result_out,
            reason=TerminationReason.EARLY,
        )
        result = bridge.execute_with_setup(tree, actor_id=ACTOR_ID)

        assert result.status == py_trees.common.Status.FAILURE
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.em_state == EM.ACTIVE  # unchanged
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
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, _ = make_case_and_embargo("rev1", em_state=EM.ACTIVE)
        dl.create(case)

        status, result_out = self._run_node(dl, case.id_)

        assert status == py_trees.common.Status.SUCCESS
        assert "error" not in result_out

    def test_returns_success_when_em_state_is_revise(self):
        """SUCCESS when case EM state is REVISE."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, _ = make_case_and_embargo("rev2", em_state=EM.REVISE)
        dl.create(case)

        status, result_out = self._run_node(dl, case.id_)

        assert status == py_trees.common.Status.SUCCESS
        assert "error" not in result_out

    def test_returns_failure_when_em_state_is_none(self):
        """FAILURE when case EM state is NONE (no active embargo)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, _ = make_case_and_embargo("rev3", em_state=EM.NONE)
        dl.create(case)

        status, result_out = self._run_node(dl, case.id_)

        assert status == py_trees.common.Status.FAILURE
        assert "error" in result_out

    def test_returns_failure_when_em_state_is_proposed(self):
        """FAILURE when case EM state is PROPOSED (initial proposal, not revision)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, _ = make_case_and_embargo("rev4", em_state=EM.PROPOSED)
        dl.create(case)

        status, result_out = self._run_node(dl, case.id_)

        assert status == py_trees.common.Status.FAILURE
        assert "error" in result_out

    def test_returns_failure_when_em_state_is_exited(self):
        """FAILURE when case EM state is EXITED."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, _ = make_case_and_embargo("rev5", em_state=EM.EXITED)
        dl.create(case)

        status, result_out = self._run_node(dl, case.id_)

        assert status == py_trees.common.Status.FAILURE
        assert "error" in result_out

    def test_error_is_invalid_state_transition(self):
        """Error in result_out is VultronInvalidStateTransitionError for bad state."""
        from vultron.errors import VultronInvalidStateTransitionError

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, _ = make_case_and_embargo("rev6", em_state=EM.NONE)
        dl.create(case)

        _, result_out = self._run_node(dl, case.id_)

        assert isinstance(
            result_out["error"], VultronInvalidStateTransitionError
        )

    def test_returns_failure_when_case_not_found(self):
        """FAILURE when the case ID does not exist in the DataLayer."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        self._setup_blackboard(dl)

        status, result_out = self._run_node(
            dl, "https://example.org/cases/nonexistent"
        )

        assert status == py_trees.common.Status.FAILURE
        assert "error" in result_out

    def test_reads_em_state_via_read_em_state_node(self):
        """AC-1: em_before in result_out is populated by ReadEmStateNode."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, _ = make_case_and_embargo("rev7", em_state=EM.ACTIVE)
        dl.create(case)

        result_out: dict = {}
        self._setup_blackboard(dl)
        node = ValidateEmbargoRevisionStateNode(
            case_id=case.id_, result_out=result_out
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert result_out.get("em_before") == EM.ACTIVE

    def test_returns_failure_when_em_state_raises_value_error(self):
        """FAILURE when ``case.em_state`` raises ValueError (no derivable EM).

        AC-3 guard: the try/except ValueError around the ``case.em_state``
        read must map to FAILURE so that callers do not attempt a revision
        proposal when the case's EM state cannot be derived (ADR-0122).
        """
        from unittest.mock import MagicMock, PropertyMock

        from vultron.core.models.case import VulnerabilityCase

        mock_case = MagicMock(spec=VulnerabilityCase)
        object.__setattr__(mock_case, "case_participants", [])
        type(mock_case).em_state = PropertyMock(
            side_effect=ValueError("no derivable EM state")
        )

        mock_dl = MagicMock()
        mock_dl.read_case.return_value = mock_case

        result_out: dict = {}
        node = ValidateEmbargoRevisionStateNode(
            case_id="https://example.org/cases/any",
            result_out=result_out,
        )
        node.datalayer = mock_dl

        result = node.update()

        assert result == py_trees.common.Status.FAILURE
        assert "error" in result_out


# ---------------------------------------------------------------------------
# SetEmbargoActiveNode — AC-1 of issue #1554
# ---------------------------------------------------------------------------


def _setup_blackboard_simple(dl: SqliteDataLayer) -> None:
    py_trees.blackboard.Blackboard.enable_activity_stream()
    py_trees.blackboard.Blackboard.storage.clear()
    bb = py_trees.blackboard.Client(name="test-sea")
    for key in ("datalayer", "actor_id"):
        bb.register_key(key=key, access=py_trees.common.Access.WRITE)
    bb.datalayer = dl
    bb.actor_id = ACTOR_ID


class TestSetEmbargoActiveNode:
    """Tests for SetEmbargoActiveNode (AC-1 of issue #1554)."""

    def _run(
        self, dl: SqliteDataLayer, case_id: str, embargo_id: str
    ) -> py_trees.common.Status:
        _setup_blackboard_simple(dl)
        node = SetEmbargoActiveNode(case_id=case_id, embargo_id=embargo_id)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()
        return node.status

    @pytest.mark.spec("EMB-02-001")
    def test_transitions_proposed_to_active(self):
        """Transitions EM.PROPOSED → EM.ACTIVE and persists."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, embargo = make_case_and_embargo("sea1", em_state=EM.PROPOSED)
        dl.create(case)
        dl.create(embargo)

        status = self._run(dl, case.id_, embargo.id_)

        assert status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.em_state == EM.ACTIVE

    def test_activation_logged_in_narrative_form(self, caplog):
        """EM PROPOSED → ACTIVE is logged at INFO (SL-04-001, AC-16)."""
        import logging

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, embargo = make_case_and_embargo(
            "sea-narrative", em_state=EM.PROPOSED
        )
        dl.create(case)
        dl.create(embargo)

        with caplog.at_level(logging.INFO):
            status = self._run(dl, case.id_, embargo.id_)

        assert status == py_trees.common.Status.SUCCESS
        narrative = [
            r
            for r in caplog.records
            if "embargo PROPOSED → ACTIVE" in r.getMessage()
            and r.levelno == logging.INFO
        ]
        assert narrative, "Expected a narrative embargo-activation line"
        message = narrative[0].getMessage()
        assert (
            message == f"Actor '{ACTOR_ID}' embargo PROPOSED → ACTIVE"
            f" for case '{case.id_}'"
        )

    def test_activated_embargo_detail_line_is_debug(self, caplog):
        """The verbose "Activated embargo ..." detail line is DEBUG."""
        import logging

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, embargo = make_case_and_embargo(
            "sea-detail", em_state=EM.PROPOSED
        )
        dl.create(case)
        dl.create(embargo)

        with caplog.at_level(logging.DEBUG):
            self._run(dl, case.id_, embargo.id_)

        detail = [
            r for r in caplog.records if "Activated embargo" in r.getMessage()
        ]
        assert detail, "Expected the 'Activated embargo' detail line"
        assert all(r.levelno == logging.DEBUG for r in detail)

    @pytest.mark.spec("EMB-18-003")
    def test_unreadable_activated_embargo_fails_without_writing(self):
        """The embargo being activated is absent: FAILURE, the case unchanged."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, embargo = make_case_and_embargo(
            "sea-missing", em_state=EM.PROPOSED
        )
        dl.create(case)

        status = self._run(dl, case.id_, embargo.id_)

        assert status == py_trees.common.Status.FAILURE
        untouched = cast(VulnerabilityCase, dl.read(case.id_))
        assert untouched.em_state == EM.PROPOSED
        assert untouched.active_embargo_id is None

    @pytest.mark.spec("EMB-18-003")
    @pytest.mark.spec("EP-05-001")
    def test_unreadable_replaced_embargo_fails_without_writing(self):
        """The embargo being replaced is absent: FAILURE, the case unchanged."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, replaced = make_case_and_embargo(
            "sea-replaced", em_state=EM.ACTIVE
        )
        revision = as_EmbargoEvent(
            id_=f"{case.id_}/embargo_events/revision",
            context=case.id_,
            end_time=days_from_now_utc(90),
        )
        propose(case, revision.id_)
        dl.create(case)
        dl.create(revision)

        status = self._run(dl, case.id_, revision.id_)

        assert status == py_trees.common.Status.FAILURE
        untouched = cast(VulnerabilityCase, dl.read(case.id_))
        assert untouched.em_state == EM.REVISE
        assert untouched.active_embargo_id == replaced.id_
        assert untouched.proposed_embargo_ids == [revision.id_]

    @pytest.mark.spec("EMB-02-001")
    def test_idempotent_when_embargo_already_active(self):
        """Returns SUCCESS without state mutation when embargo is already active."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, embargo = make_case_and_embargo("sea2", em_state=EM.ACTIVE)
        dl.create(case)

        status = self._run(dl, case.id_, embargo.id_)

        assert status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.em_state == EM.ACTIVE

    def test_delegates_em_activation_to_embargo_lifecycle(self):
        """EMB-18-001 (issue #2696): update() delegates to EmbargoLifecycle.activate_embargo()."""
        from unittest.mock import patch

        from vultron.core.services.embargo_lifecycle import (
            EmbargoLifecycle,
            EmbargoLifecycleResult,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, embargo = make_case_and_embargo("sea3", em_state=EM.PROPOSED)
        dl.create(case)

        _setup_blackboard_simple(dl)
        node = SetEmbargoActiveNode(case_id=case.id_, embargo_id=embargo.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        fake_result = EmbargoLifecycleResult(
            em_before=EM.PROPOSED,
            em_after=EM.ACTIVE,
            case_changed=True,
            case_embargo_changed=True,
        )
        with patch.object(
            EmbargoLifecycle,
            "activate_embargo",
            return_value=fake_result,
        ) as mock_activate:
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert mock_activate.called, (
            "EmbargoLifecycle.activate_embargo() was never called"
        )

    def test_idempotent_guard_does_not_skip_a_revision_in_revise(self):
        """In REVISE the guard skips only the embargo already in force (#2859).

        A revision is its own register entry (ADR-0122), so activating the
        open revision while another embargo is ACTIVE must call
        activate_embargo() rather than returning early.
        """
        from unittest.mock import patch

        from vultron.core.services.embargo_lifecycle import (
            EmbargoLifecycle,
            EmbargoLifecycleResult,
        )

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
        case, _embargo = make_case_and_embargo("sea-2859", em_state=EM.REVISE)
        (revision_id,) = case.proposed_embargo_ids
        dl.create(case)

        _setup_blackboard_simple(dl)
        node = SetEmbargoActiveNode(case_id=case.id_, embargo_id=revision_id)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        fake_result = EmbargoLifecycleResult(
            em_before=EM.REVISE,
            em_after=EM.ACTIVE,
            case_changed=True,
            case_embargo_changed=False,
        )
        with patch.object(
            EmbargoLifecycle,
            "activate_embargo",
            return_value=fake_result,
        ) as mock_activate:
            bt.tick()

        assert mock_activate.called, (
            "activate_embargo() was not called — idempotency guard skipped"
            " the open revision"
        )

    def test_returns_failure_when_case_missing(self):
        """Returns FAILURE when the case is not found in the DataLayer."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )

        status = self._run(
            dl,
            "https://example.org/cases/nonexistent",
            "https://example.org/cases/nonexistent/embargo_events/e1",
        )

        assert status == py_trees.common.Status.FAILURE

    @pytest.mark.spec("EMB-18-002")
    def test_returns_failure_on_invalid_em_transition(self, caplog):
        """EMB-18-002: returns FAILURE for non-standard EM transitions (not warning-only)."""
        import logging

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, embargo = make_case_and_embargo("sea5", em_state=EM.NONE)
        dl.create(case)

        _setup_blackboard_simple(dl)
        node = SetEmbargoActiveNode(case_id=case.id_, embargo_id=embargo.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.WARNING):
            bt.tick()

        assert node.status == py_trees.common.Status.FAILURE
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.em_state == EM.NONE

    def test_returns_failure_when_em_state_raises_value_error(self):
        """FAILURE when ``case.em_state`` raises ValueError (no derivable EM).

        Regression test for issue #2742: activate_embargo() reads
        ``case.em_state`` internally.  A ValueError from that read must be
        caught and mapped to Status.FAILURE, not propagate as an uncaught
        exception.
        """
        from unittest.mock import MagicMock, PropertyMock

        from vultron.core.models.case import VulnerabilityCase

        mock_case = MagicMock(spec=VulnerabilityCase)
        object.__setattr__(mock_case, "case_participants", [])
        type(mock_case).active_embargo = PropertyMock(return_value=None)
        type(mock_case).em_state = PropertyMock(
            side_effect=ValueError("no derivable EM state")
        )

        mock_dl = MagicMock()
        mock_dl.read_case.return_value = mock_case

        node = SetEmbargoActiveNode(
            case_id="https://example.org/cases/any",
            embargo_id="https://example.org/cases/any/embargo_events/e1",
        )
        node.datalayer = mock_dl

        result = node.update()

        assert result == py_trees.common.Status.FAILURE

    @pytest.mark.spec("EMB-18-001")
    def test_em_write_goes_through_embargo_lifecycle(self):
        """EMB-18-001: EM write is delegated to EmbargoLifecycle.activate_embargo().

        Patch EmbargoLifecycle.activate_embargo() and confirm it is invoked
        during the PROPOSED → ACTIVE transition, proving that EM writes route
        through the service layer (not inline mutation) (EMB-18-001).
        """
        from unittest.mock import patch

        from vultron.core.services.embargo_lifecycle import (
            EmbargoLifecycle,
            EmbargoLifecycleResult,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=ACTOR_ID,
        )
        case, embargo = make_case_and_embargo("sea-ac1", em_state=EM.PROPOSED)
        dl.create(case)

        _setup_blackboard_simple(dl)
        node = SetEmbargoActiveNode(case_id=case.id_, embargo_id=embargo.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        fake_result = EmbargoLifecycleResult(
            em_before=EM.PROPOSED,
            em_after=EM.ACTIVE,
            case_changed=True,
            case_embargo_changed=True,
        )
        with patch.object(
            EmbargoLifecycle,
            "activate_embargo",
            return_value=fake_result,
        ) as mock_activate:
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert mock_activate.called, (
            "EmbargoLifecycle.activate_embargo() was never called"
        )


class TestProposeEmbargoLifecycleNodeOnBehalfOfAProposer:
    """``proposer_id`` names whose terms these are when the manager adjudicates."""

    PROPOSER = "https://example.org/actors/proposer"

    def _case(self) -> tuple[SqliteDataLayer, VulnerabilityCase, str]:
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_MANAGER_ACTOR)
        case, embargo = make_case_and_embargo("obo1", em_state=EM.ACTIVE)
        manager = as_CaseParticipant(
            id_=f"{case.id_}/participants/cm",
            attributed_to=CASE_MANAGER_ACTOR,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        proposer = as_CaseParticipant(
            id_=f"{case.id_}/participants/proposer",
            attributed_to=self.PROPOSER,
            context=case.id_,
        )
        for p in (manager, proposer):
            case.case_participants.append(p.id_)
            case.actor_participant_index[cast(str, p.attributed_to)] = p.id_
            dl.create(p)
        dl.create(case)
        dl.create(embargo)
        revision = as_EmbargoEvent(
            id_=f"{case.id_}/embargo_events/revision",
            context=case.id_,
            end_time=days_from_now_utc(90),
        )
        dl.create(revision)
        return dl, case, revision.id_

    def _run(
        self, dl: SqliteDataLayer, node: ProposeEmbargoLifecycleNode
    ) -> py_trees.common.Status:
        return (
            BTBridge(datalayer=dl, sync_port=SyncActivityAdapter(dl))
            .execute_with_setup(tree=node, actor_id=CASE_MANAGER_ACTOR)
            .status
        )

    def _accepted(self, dl: SqliteDataLayer, case_id: str, actor: str):
        case = cast(VulnerabilityCase, dl.read(case_id))
        participant = dl.read(case.actor_participant_index[actor])
        assert isinstance(participant, CaseParticipant)
        return [
            embargo_id
            for embargo_id in (
                row.embargo_id for row in participant.embargo_consents
            )
            if participant.consent_for(embargo_id)
            is EmbargoConsentState.ACCEPTED
        ]

    @pytest.mark.spec("EP-09-001")
    def test_the_proposers_consent_is_recorded_not_the_managers(self):
        dl, case, revision_id = self._case()
        result_out: dict[str, object] = {}
        status = self._run(
            dl,
            ProposeEmbargoLifecycleNode(
                case_id=case.id_,
                embargo_id=revision_id,
                result_out=result_out,
                proposer_id=self.PROPOSER,
            ),
        )
        assert status is py_trees.common.Status.SUCCESS
        assert result_out["em_after"] is EM.REVISE
        assert revision_id in self._accepted(dl, case.id_, self.PROPOSER)
        assert revision_id not in self._accepted(
            dl, case.id_, CASE_MANAGER_ACTOR
        )

    def test_without_a_proposer_the_executing_actor_proposes(self):
        dl, case, revision_id = self._case()
        status = self._run(
            dl,
            ProposeEmbargoLifecycleNode(
                case_id=case.id_, embargo_id=revision_id, result_out={}
            ),
        )
        assert status is py_trees.common.Status.SUCCESS
        assert revision_id in self._accepted(dl, case.id_, CASE_MANAGER_ACTOR)
