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

import logging
from typing import cast
from unittest.mock import MagicMock

import py_trees

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes.lifecycle import (
    TerminateEmbargoNode,
    ValidateEmbargoRevisionStateNode,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

from test.core.behaviors.embargo.nodes.conftest import (
    make_case_and_embargo,
    setup_blackboard,
)


class TestTerminateEmbargoNode:
    """Tests for TerminateEmbargoNode (trigger-side embargo teardown)."""

    def test_terminates_active_embargo(self):
        """Node transitions ACTIVE → EXITED, clears active_embargo, returns SUCCESS."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, embargo = make_case_and_embargo("ten1", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = TerminateEmbargoNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em_state == EM.EXITED
        assert updated.active_embargo is None

    def test_terminates_revise_embargo(self):
        """Node transitions REVISE → EXITED, returns SUCCESS."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, embargo = make_case_and_embargo("ten2", em_state=EM.REVISE)
        dl.create(case)

        setup_blackboard(dl)
        node = TerminateEmbargoNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em_state == EM.EXITED
        assert updated.active_embargo is None

    def test_returns_success_when_no_active_embargo(self):
        """Node returns SUCCESS without changes when no active embargo."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("ten3", em_state=EM.NONE)
        case.active_embargo = None
        dl.create(case)

        setup_blackboard(dl)
        node = TerminateEmbargoNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em_state == EM.NONE  # unchanged

    def test_returns_success_when_invalid_transition(self, caplog):
        """Node returns SUCCESS (non-fatal) when EM transition is blocked."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, embargo = make_case_and_embargo("ten4", em_state=EM.PROPOSED)
        dl.create(case)

        setup_blackboard(dl)
        node = TerminateEmbargoNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.WARNING):
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert any(
            "EXITED" in r.message or "blocked" in r.message
            for r in caplog.records
        )

    def test_returns_success_when_case_missing(self):
        """Node returns SUCCESS when case is not found in DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")

        setup_blackboard(dl)
        node = TerminateEmbargoNode(
            case_id="https://example.org/cases/nonexistent"
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_success_when_case_id_is_none(self):
        """Node returns SUCCESS immediately when case_id is None."""
        dl = SqliteDataLayer("sqlite:///:memory:")

        setup_blackboard(dl)
        node = TerminateEmbargoNode(case_id=None)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_resets_participant_pec_state(self):
        """Node resets participant embargo_consent_state to NO_EMBARGO."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("ten6", em_state=EM.ACTIVE)
        participant = CaseParticipant(
            id_=f"{case.id_}/participants/p1",
            attributed_to="https://example.org/users/vendor",
        )
        participant.embargo_consent_state = PEC.SIGNATORY.value
        case.case_participants.append(participant.id_)
        dl.create(case)
        dl.create(participant)

        setup_blackboard(dl)
        node = TerminateEmbargoNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated_p = cast(CaseParticipant, dl.read(participant.id_))
        assert updated_p.embargo_consent_state == PEC.NO_EMBARGO.value

    def test_queues_activity_to_case_manager_outbox(self):
        """When trigger_activity_factory is present, terminate_embargo is called."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("ten7", em_state=EM.ACTIVE)

        case_manager_participant = CaseParticipant(
            id_=f"{case.id_}/participants/cm",
            attributed_to="https://example.org/actors/case-manager",
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case.case_participants.append(case_manager_participant.id_)
        case.actor_participant_index[
            "https://example.org/actors/case-manager"
        ] = case_manager_participant.id_
        dl.create(case)
        dl.create(case_manager_participant)

        py_trees.blackboard.Blackboard.enable_activity_stream()
        blackboard = py_trees.blackboard.Client(name="test-setup-ten7")
        for key in ("datalayer", "actor_id", "trigger_activity_factory"):
            blackboard.register_key(
                key=key, access=py_trees.common.Access.WRITE
            )
        blackboard.datalayer = dl
        blackboard.actor_id = "https://example.org/actors/case-manager"

        factory = MagicMock()
        activity_id = "https://example.org/activities/act1"
        factory.terminate_embargo.return_value = (activity_id, {})
        blackboard.trigger_activity_factory = factory

        node = TerminateEmbargoNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        factory.terminate_embargo.assert_called_once()


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
