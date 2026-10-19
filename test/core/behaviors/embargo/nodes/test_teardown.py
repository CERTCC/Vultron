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

"""Unit tests for embargo teardown nodes (teardown.py)."""

import logging
from typing import cast
from unittest.mock import MagicMock, patch

import py_trees
import pytest

from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    make_case_and_embargo,
    make_case_with_manager,
    setup_blackboard,
)
from test.support.embargo_register import propose
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes import EMBARGO_TEARDOWN_SEMANTIC_TYPE
from vultron.core.behaviors.embargo.nodes.teardown import (
    ApplyEmbargoTeardownNode,
    ClearActiveEmbargoNode,
    HasEmbargoActiveNode,
    SendAnnounceEmbargoEventNode,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant

ACTOR_ID = "https://example.org/actors/vendor"


def _e1(case: VulnerabilityCase) -> str:
    """The id of the embargo ``make_case_and_embargo`` puts in force."""
    return f"{case.id_}/embargo_events/e1"


def _setup_blackboard_with_factory(
    dl: SqliteDataLayer,
    factory: MagicMock,
    actor_id: str = ACTOR_ID,
) -> None:
    """Write datalayer, actor_id, and trigger_activity_factory to blackboard."""
    py_trees.blackboard.Blackboard.enable_activity_stream()
    bb = py_trees.blackboard.Client(name="test-factory-setup")
    for key in ("datalayer", "actor_id", "trigger_activity_factory"):
        bb.register_key(key=key, access=py_trees.common.Access.WRITE)
    bb.datalayer = dl
    bb.actor_id = actor_id
    bb.trigger_activity_factory = factory


class TestHasEmbargoActiveNode:
    """Tests for HasEmbargoActiveNode."""

    def test_returns_success_when_em_active(self):
        """Returns SUCCESS when EM state is ACTIVE."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("hea1", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = HasEmbargoActiveNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_success_when_em_revise(self):
        """Returns SUCCESS when EM state is REVISE (also an active embargo)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("hea2", em_state=EM.REVISE)
        dl.create(case)

        setup_blackboard(dl)
        node = HasEmbargoActiveNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_failure_when_em_exited(self):
        """Returns FAILURE when EM state is EXITED (teardown already done)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("hea3", em_state=EM.EXITED)
        dl.create(case)

        setup_blackboard(dl)
        node = HasEmbargoActiveNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE

    def test_returns_failure_when_case_missing(self):
        """Returns FAILURE when case is not found in the DataLayer."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        setup_blackboard(dl)

        node = HasEmbargoActiveNode(
            case_id="https://example.org/cases/nonexistent"
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE


class TestClearActiveEmbargoNode:
    """Tests for ClearActiveEmbargoNode."""

    @pytest.mark.spec("EMB-07-001")
    def test_transitions_em_active_to_exited_and_clears_pointer(self):
        """Terminates the ACTIVE entry: EM derives EXITED and no embargo is active."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen1", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(
            case_id=case.id_,
            embargo_id=_e1(case),
            termination=EmbargoTermination.early(),
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED
        assert updated.active_embargo is None

    @pytest.mark.spec("EP-08-003")
    @pytest.mark.spec("EP-08-004")
    def test_teardown_forgets_every_open_revision(self):
        """The replay path cancels every open revision and prunes the index.

        ``ClearActiveEmbargoNode`` applies the ``TERMINATE`` step through
        the one apply function, so the embargo in force is terminated and
        every open revision of it cancelled in one register step — the same
        step the trigger side applies (EP-08-004, ADR-0113, ADR-0122,
        ADR-0124).  Each cancelled proposal
        leaves the open-proposal index too (EP-08-003).
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _embargo = make_case_and_embargo("caen1r", em_state=EM.ACTIVE)
        revisions = [
            f"{case.id_}/embargo_events/revision",
            f"{case.id_}/embargo_events/revision2",
        ]
        propose(case, *revisions)
        case.pending_embargo_proposal_index = {
            rid: f"{rid}/proposal" for rid in revisions
        }
        assert case.em_state == EM.REVISE
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(
            case_id=case.id_,
            embargo_id=_e1(case),
            termination=EmbargoTermination.early(),
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.em_state == EM.EXITED
        assert updated.active_embargo is None
        assert updated.proposed_embargo_ids == []
        assert updated.pending_embargo_proposal_index == {}
        assert {
            e.embargo_id: e.status
            for e in updated.embargo_register
            if e.embargo_id in revisions
        } == {rid: EmbargoRegisterStatus.CANCELLED for rid in revisions}

    def test_teardown_logged_in_narrative_form(self, caplog):
        """EM ACTIVE → EXITED is logged at INFO (SL-04-001, AC-16)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen-narr", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl, actor_id=ACTOR_ID)
        node = ClearActiveEmbargoNode(
            case_id=case.id_,
            embargo_id=_e1(case),
            termination=EmbargoTermination.early(),
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.INFO):
            bt.tick()

        narrative = [
            r
            for r in caplog.records
            if "embargo ACTIVE → EXITED" in r.getMessage()
            and r.levelno == logging.INFO
        ]
        assert narrative, "Expected a narrative embargo-teardown line"
        assert (
            narrative[0].getMessage()
            == f"Actor '{ACTOR_ID}' embargo ACTIVE → EXITED"
            f" for case '{case.id_}'"
        )

    def test_cleared_embargo_detail_line_is_debug(self, caplog):
        """The verbose "Cleared active embargo" detail line is DEBUG."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen-detail", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(
            case_id=case.id_,
            embargo_id=_e1(case),
            termination=EmbargoTermination.early(),
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.DEBUG):
            bt.tick()

        detail = [
            r
            for r in caplog.records
            if "Cleared active embargo" in r.getMessage()
        ]
        assert detail, "Expected the 'Cleared active embargo' detail line"
        assert all(r.levelno == logging.DEBUG for r in detail)

    @pytest.mark.spec("EMB-07-002")
    def test_transitions_em_revise_to_exited(self):
        """Transitions EM.REVISE → EXITED."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen2", em_state=EM.REVISE)
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(
            case_id=case.id_,
            embargo_id=_e1(case),
            termination=EmbargoTermination.early(),
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED

    @pytest.mark.spec("EMB-07-003")
    def test_idempotent_when_already_exited(self):
        """Returns SUCCESS without modifying state when EM already EXITED."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen3", em_state=EM.EXITED)
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(
            case_id=case.id_,
            embargo_id=_e1(case),
            termination=EmbargoTermination.early(),
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED

    def test_state_sync_override_for_unexpected_em_state(self, caplog):
        """A teardown with no embargo in force is logged and changes nothing.

        The register refuses to terminate an embargo that is not ``ACTIVE``
        (ADR-0122), so the step is skipped, leaving the case as it was.
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen4", em_state=EM.NONE)
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(
            case_id=case.id_,
            embargo_id=_e1(case),
            termination=EmbargoTermination.early(),
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with caplog.at_level(logging.INFO):
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert not node.applied
        assert "teardown skipped" in node.feedback_message
        assert not any(
            "Cleared active embargo" in r.getMessage() for r in caplog.records
        )
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.em_state == EM.NONE
        assert updated.embargo_register == []

    @pytest.mark.spec("CM-23-016")
    def test_ends_only_the_embargo_the_remove_names(self):
        """A ``Remove`` naming an embargo not in force ends nothing, even
        though another embargo is in force (ADR-0122, #4294 AC-3)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen-named", em_state=EM.REVISE)
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(
            case_id=case.id_,
            embargo_id=f"{case.id_}/embargo_events/e2",
            termination=EmbargoTermination.early(),
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert not node.applied
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.em_state == EM.REVISE
        assert updated.active_embargo_id == _e1(case)

    def test_returns_failure_when_case_missing(self):
        """Returns FAILURE when the case is not found in the DataLayer."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        setup_blackboard(dl)

        node = ClearActiveEmbargoNode(
            case_id="https://example.org/cases/nonexistent",
            embargo_id="https://example.org/cases/nonexistent/embargo_events/e1",
            termination=EmbargoTermination.early(),
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE

    def test_single_save_call(self):
        """The register step deriving EM EXITED is saved in one write."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen5", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(
            case_id=case.id_,
            embargo_id=_e1(case),
            termination=EmbargoTermination.early(),
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        writes: list[object] = []
        original_save, original_save_many = dl.save, dl.save_many

        def recording_save(obj):
            writes.append(obj)
            return original_save(obj)

        def recording_save_many(objs):
            writes.append(list(objs))
            return original_save_many(objs)

        dl.save = recording_save
        dl.save_many = recording_save_many
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert len(writes) == 1, f"Expected exactly 1 write, got {writes}"

    @pytest.mark.spec("CM-23-016")
    def test_writes_through_the_one_apply_function(self):
        """The step is applied by ``apply_embargo_change`` (ADR-0124); a
        step it refuses is a refusal, and nothing is written."""
        from vultron.core.behaviors.embargo.nodes import teardown
        from vultron.errors import VultronEntryRefusedError

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("caen-apply", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = ClearActiveEmbargoNode(
            case_id=case.id_,
            embargo_id=_e1(case),
            termination=EmbargoTermination.early(),
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        with patch.object(
            teardown,
            "apply_embargo_change",
            side_effect=VultronEntryRefusedError("refused"),
        ):
            bt.tick()

        assert node.status == py_trees.common.Status.FAILURE
        assert node.refused
        unchanged = cast(VulnerabilityCase, dl.read(case.id_))
        assert unchanged.current_status.em.state == EM.ACTIVE


def _remove_entry(
    case_id: str, embargo_id: str | None, content: object = "EARLY"
) -> CaseLedgerEntry:
    """The CASE_MANAGER's ``Remove(EmbargoEvent)`` entry naming *embargo_id*."""
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=case_id,
            log_index=0,
            object_id=f"{case_id}/activities/remove",
            semantic_type=EMBARGO_TEARDOWN_SEMANTIC_TYPE,
            payload_snapshot={
                "type": "Remove",
                "object": (
                    {"id": embargo_id, "type": "EmbargoEvent"}
                    if embargo_id is not None
                    else None
                ),
                "content": content,
                "published": now_utc().isoformat(),
                "context": case_id,
            },
            prev_log_hash="0" * 64,
        )
    )


def _copy_node(
    dl: SqliteDataLayer, entry: CaseLedgerEntry
) -> ApplyEmbargoTeardownNode:
    node = ApplyEmbargoTeardownNode()
    node.datalayer = dl
    node.actor_id = ACTOR_ID
    node.activity = type("Carrier", (), {"log_entry": entry})()
    return node


class TestApplyEmbargoTeardownNode:
    """The ``EmbargoTeardown`` replica slot copies a ``Remove`` entry."""

    @staticmethod
    def _store(
        suffix: str, em_state: EM
    ) -> tuple[SqliteDataLayer, VulnerabilityCase]:
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, embargo = make_case_and_embargo(suffix, em_state=em_state)
        dl.create(case)
        dl.create(embargo)
        return dl, case

    @pytest.mark.spec("EMB-07-001")
    @pytest.mark.spec("CM-23-016")
    def test_transitions_em_active_to_exited(self):
        """The entry's step terminates the embargo it names: EXITED."""
        dl, case = self._store("atn1", EM.ACTIVE)

        status = _copy_node(dl, _remove_entry(case.id_, _e1(case))).update()

        assert status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED
        assert updated.active_embargo is None
        assert updated.embargo_termination == EmbargoTermination.early()

    def test_teardown_logged_at_info(self, caplog):
        """The copied teardown is a lifecycle milestone, logged at INFO."""
        dl, case = self._store("atn-log", EM.ACTIVE)

        with caplog.at_level(logging.INFO):
            _copy_node(dl, _remove_entry(case.id_, _e1(case))).update()

        assert any(
            r.levelno == logging.INFO
            and "copied" in r.getMessage()
            and case.id_ in r.getMessage()
            for r in caplog.records
        )

    @pytest.mark.spec("EMB-07-002")
    @pytest.mark.spec("EP-08-004")
    def test_transitions_em_revise_to_exited_cancelling_the_revision(self):
        """REVISE → EXITED: the open revision is cancelled in the same step."""
        dl, case = self._store("atn2", EM.REVISE)

        status = _copy_node(dl, _remove_entry(case.id_, _e1(case))).update()

        assert status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED
        assert updated.proposed_embargo_ids == []
        statuses = {e.embargo_id: e.status for e in updated.embargo_register}
        assert statuses[f"{case.id_}/embargo_events/e2"] is (
            EmbargoRegisterStatus.CANCELLED
        )

    @pytest.mark.spec("EMB-07-003")
    def test_idempotent_when_already_exited(self):
        """An entry whose embargo has already ended changes nothing."""
        dl, case = self._store("atn3", EM.EXITED)
        before = cast(VulnerabilityCase, dl.read(case.id_)).embargo_register

        status = _copy_node(dl, _remove_entry(case.id_, _e1(case))).update()

        assert status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.embargo_register == before

    @pytest.mark.spec("CM-23-016")
    def test_ends_the_embargo_the_entry_names_never_the_local_one(self):
        """An entry naming an embargo not in force here ends nothing, even
        with another in force (#4294 AC-3): as on the CASE_MANAGER, where
        such a ``Remove`` is ledgered with no effect (CLP-02-013)."""
        dl, case = self._store("atn-named", EM.REVISE)
        node = _copy_node(
            dl, _remove_entry(case.id_, f"{case.id_}/embargo_events/e2")
        )

        status = node.update()

        assert status == py_trees.common.Status.SUCCESS
        assert "not the one in force" in node.feedback_message
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.em_state == EM.REVISE
        assert updated.active_embargo_id == _e1(case)

    @pytest.mark.spec("EMB-13-001")
    def test_leaves_consent_rows_and_leaves_nobody_a_signatory(self):
        """Teardown writes no consent: rows stay, but no embargo is in force."""
        dl, case = self._store("atn5", EM.ACTIVE)
        participant = as_CaseParticipant(
            id_=f"{case.id_}/participants/p1",
            attributed_to="https://example.org/users/finder",
            embargo_consents=[
                EmbargoConsent(
                    embargo_id=_e1(case), state=EmbargoConsentState.AGREED
                )
            ],
        )
        stored = cast(VulnerabilityCase, dl.read(case.id_))
        stored.case_participants.append(participant.id_)
        stored.actor_participant_index["https://example.org/users/finder"] = (
            participant.id_
        )
        dl.save(stored)
        dl.create(participant)
        assert participant.is_signatory(stored.active_embargo_id)

        status = _copy_node(dl, _remove_entry(case.id_, _e1(case))).update()

        assert status == py_trees.common.Status.SUCCESS
        updated_case = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated_case.active_embargo_id is None
        updated_p = cast(as_CaseParticipant, dl.read(participant.id_))
        assert updated_p.embargo_consents == participant.embargo_consents
        assert not updated_p.is_signatory(updated_case.active_embargo_id)

    def test_returns_success_when_case_missing(self):
        """A case this replica does not hold is skipped (Regime 2)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        missing = "https://example.org/cases/nonexistent"

        status = _copy_node(
            dl, _remove_entry(missing, f"{missing}/embargo_events/e1")
        ).update()

        assert status == py_trees.common.Status.SUCCESS

    @pytest.mark.parametrize(
        ("content", "names_embargo"),
        [(None, True), ("THREAT_SIGNAL", True), ("EARLY", False)],
    )
    def test_refuses_a_malformed_entry(self, content, names_embargo):
        """No termination reason, or no embargo named: FAILURE, unchanged."""
        dl, case = self._store("atn-bad", EM.ACTIVE)
        entry = _remove_entry(
            case.id_, _e1(case) if names_embargo else None, content
        )

        status = _copy_node(dl, entry).update()

        assert status == py_trees.common.Status.FAILURE
        assert cast(VulnerabilityCase, dl.read(case.id_)).em_state is (
            EM.ACTIVE
        )

    @pytest.mark.spec("EMB-18-003")
    def test_refuses_an_end_time_entry_whose_embargo_it_cannot_read(self):
        """An ``END_TIME_REACHED`` against an unreadable embargo fails
        closed: FAILURE, nothing written, nothing raised."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _embargo = make_case_and_embargo(
            "atn-unread", em_state=EM.ACTIVE
        )
        dl.create(case)  # the embargo record itself is not stored
        node = _copy_node(
            dl, _remove_entry(case.id_, _e1(case), "END_TIME_REACHED")
        )

        status = node.update()

        assert status == py_trees.common.Status.FAILURE
        assert "Refused teardown entry" in node.feedback_message
        assert cast(VulnerabilityCase, dl.read(case.id_)).em_state is (
            EM.ACTIVE
        )

    @pytest.mark.spec("CM-23-016")
    def test_a_step_the_apply_function_refuses_is_held_for_gap_handling(self):
        """Refused into the gap buffer, never patched over (ADR-0124)."""
        from vultron.core.models.ledger_gap_buffer import LedgerGapBuffer
        from vultron.errors import VultronEntryRefusedError

        dl, case = self._store("atn-gap", EM.ACTIVE)
        node = _copy_node(dl, _remove_entry(case.id_, _e1(case)))
        gap_buffer = LedgerGapBuffer()
        node._gap_buffer = gap_buffer

        with patch(
            "vultron.core.behaviors.sync.nodes.embargo_copy_effect"
            ".apply_embargo_change",
            side_effect=VultronEntryRefusedError("diverged"),
        ):
            status = node.update()

        assert status == py_trees.common.Status.FAILURE
        assert node.refused_into_gap
        assert gap_buffer.depth(case.id_) == 1
        assert cast(VulnerabilityCase, dl.read(case.id_)).em_state is (
            EM.ACTIVE
        )


# ---------------------------------------------------------------------------
# SendAnnounceEmbargoEventNode
# ---------------------------------------------------------------------------


class TestSendAnnounceEmbargoEventNode:
    """Tests for SendAnnounceEmbargoEventNode."""

    def _make_factory(self) -> MagicMock:
        factory = MagicMock()
        factory.announce_embargo.return_value = (
            "https://example.org/activities/announce1",
            {},
        )
        return factory

    def test_emits_announce_activity_and_queues_to_outbox(self):
        """Node calls announce_embargo and queues the activity to outbox."""
        case, _, dl = make_case_with_manager("saee1", em_state=EM.ACTIVE)
        _, embargo = make_case_and_embargo("saee1")
        factory = self._make_factory()

        _setup_blackboard_with_factory(dl, factory)
        node = SendAnnounceEmbargoEventNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        factory.announce_embargo.assert_called_once_with(
            embargo_id=embargo.id_,
            case_id=case.id_,
            actor=ACTOR_ID,
            to=[CASE_MANAGER_ACTOR],
        )
        outbox = dl.outbox_list()
        assert "https://example.org/activities/announce1" in outbox

    def test_returns_success_when_factory_unavailable(self):
        """Node returns SUCCESS (skips gracefully) when no factory is set."""
        case, _, dl = make_case_with_manager("saee2", em_state=EM.ACTIVE)
        _, embargo = make_case_and_embargo("saee2")

        setup_blackboard(dl, actor_id=ACTOR_ID)
        node = SendAnnounceEmbargoEventNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_failure_when_case_not_found(self):
        """Node returns FAILURE when the case cannot be read from the DataLayer."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        factory = self._make_factory()

        _setup_blackboard_with_factory(dl, factory)
        node = SendAnnounceEmbargoEventNode(
            case_id="https://example.org/cases/missing",
            embargo_id="https://example.org/cases/missing/embargo_events/e1",
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE
        factory.announce_embargo.assert_not_called()

    def test_returns_success_when_no_case_manager(self):
        """Node returns SUCCESS (skips gracefully) when no CASE_MANAGER is found."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, embargo = make_case_and_embargo("saee4", em_state=EM.ACTIVE)
        dl.create(case)  # no CASE_MANAGER participant
        factory = self._make_factory()

        _setup_blackboard_with_factory(dl, factory)
        node = SendAnnounceEmbargoEventNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        factory.announce_embargo.assert_not_called()

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "CM-24-006: SendAnnounceEmbargoEventNode returns SUCCESS with a "
            "warning when the roster names no CASE_MANAGER. Tracked by #3964 "
            "(Concern #3918, ADR-0113)."
        ),
    )
    @pytest.mark.spec("CM-24-006")
    def test_fails_when_no_case_manager(self):
        """A roster with no CASE_MANAGER is a fault: FAILURE, not a skip."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, embargo = make_case_and_embargo("saee4b", em_state=EM.ACTIVE)
        dl.create(case)  # no CASE_MANAGER participant
        factory = self._make_factory()

        _setup_blackboard_with_factory(dl, factory)
        node = SendAnnounceEmbargoEventNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE
        factory.announce_embargo.assert_not_called()

    def test_returns_failure_when_factory_raises(self):
        """Node returns FAILURE when the factory call raises an exception."""
        case, _, dl = make_case_with_manager("saee5", em_state=EM.ACTIVE)
        _, embargo = make_case_and_embargo("saee5")
        factory = self._make_factory()
        factory.announce_embargo.side_effect = RuntimeError("boom")

        _setup_blackboard_with_factory(dl, factory)
        node = SendAnnounceEmbargoEventNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE

    def test_returns_success_when_outbox_write_fails(self):
        """Node returns SUCCESS (best-effort) when factory succeeds but outbox write raises."""
        case, _, dl = make_case_with_manager("saee6", em_state=EM.ACTIVE)
        _, embargo = make_case_and_embargo("saee6")
        factory = self._make_factory()

        _setup_blackboard_with_factory(dl, factory)
        node = SendAnnounceEmbargoEventNode(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()

        patch_target = (
            "vultron.core.behaviors.embargo.nodes.emit.add_activity_to_outbox"
        )
        with patch(patch_target, side_effect=RuntimeError("outbox error")):
            bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        factory.announce_embargo.assert_called_once()
