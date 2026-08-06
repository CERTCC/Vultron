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

"""Tests for idempotency guard nodes satisfying CLP-13-001/CLP-13-002.

AC-1: Guard nodes return FAILURE with no CaseLedgerEntry written on true-duplicate fire.
AC-2: Guard nodes inherit SilentIdempotencyGuardMixin.
AC-3: CLP-13-001 and CLP-13-002 satisfied.
"""

from py_trees.common import Status

from vultron.core.behaviors.case.accept_invite_tree import (
    CheckInviteeNotAlreadyParticipantNode,
)
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.behaviors.status.nodes.case_status import (
    CheckCaseStatusIdempotencyNode,
    CASE_STATUS_ALREADY_PRESENT,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.vultron_types import VultronParticipant
from test.core.behaviors.bt_harness import BTTestScenario

_CASE_ID = "https://example.org/cases/case-001"
_INVITEE_ID = "https://example.org/actors/invitee"
_ACTOR_ID = "https://example.org/actors/vendor"


# ---------------------------------------------------------------------------
# SilentIdempotencyGuardMixin — AC-2 (structural)
# ---------------------------------------------------------------------------


class TestSilentIdempotencyGuardMixinMembership:
    """CLP-13-002: guard nodes MUST inherit SilentIdempotencyGuardMixin."""

    def test_check_invitee_not_already_participant_uses_mixin(self) -> None:
        assert issubclass(
            CheckInviteeNotAlreadyParticipantNode, SilentIdempotencyGuardMixin
        )

    def test_check_case_status_idempotency_uses_mixin(self) -> None:
        assert issubclass(
            CheckCaseStatusIdempotencyNode, SilentIdempotencyGuardMixin
        )


# ---------------------------------------------------------------------------
# CheckInviteeNotAlreadyParticipantNode — AC-1
# ---------------------------------------------------------------------------


def _seed_case_with_participant(
    bt_scenario: BTTestScenario,
    *,
    backfill_complete: bool = True,
) -> VulnerabilityCase:
    """Seed a case that already has the invitee as a participant."""
    from vultron.core.models.replication_state import VultronReplicationState

    participant = VultronParticipant(
        id_=f"{_CASE_ID}/participants/invitee",
        attributed_to=_INVITEE_ID,
        context=_CASE_ID,
    )
    case = VulnerabilityCase(
        id_=_CASE_ID,
        name="Test Case",
    )
    case.add_participant(participant)
    bt_scenario.dl.create(participant)
    bt_scenario.dl.create(case)

    if backfill_complete:
        state = VultronReplicationState(
            case_id=_CASE_ID,
            peer_id=_INVITEE_ID,
            join_backfill_target_index=0,
            join_backfill_last_sent_index=0,
            join_backfill_complete=True,
        )
        bt_scenario.dl.save(state)

    return case


def _seed_fresh_case(bt_scenario: BTTestScenario) -> VulnerabilityCase:
    """Seed a case with no participants."""
    case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
    bt_scenario.dl.create(case)
    return case


class TestCheckInviteeNotAlreadyParticipantNode:
    """CLP-13-001: guard FAILURE must not call create_commit_log_entry_tree."""

    def test_returns_failure_when_backfill_complete_duplicate(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """True duplicate (backfill complete) → FAILURE."""
        _seed_case_with_participant(bt_scenario, backfill_complete=True)
        node = CheckInviteeNotAlreadyParticipantNode(
            case_id=_CASE_ID, invitee_id=_INVITEE_ID
        )
        result = bt_scenario.run(node, actor_id=_ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_no_ledger_entry_written_on_true_duplicate(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """AC-1: no CaseLedgerEntry is written to the datalayer when a duplicate fires."""
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        _seed_case_with_participant(bt_scenario, backfill_complete=True)
        node = CheckInviteeNotAlreadyParticipantNode(
            case_id=_CASE_ID, invitee_id=_INVITEE_ID
        )
        bt_scenario.run(node, actor_id=_ACTOR_ID)
        entries = [
            obj
            for obj in bt_scenario.dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry) and obj.case_id == _CASE_ID
        ]
        assert (
            entries == []
        ), f"Guard wrote {len(entries)} ledger entry/entries — CLP-13-001 violated"

    def test_returns_success_for_backfill_incomplete_resume_no_state(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Resume path (no replication state marker) → SUCCESS, tree continues."""
        _seed_case_with_participant(bt_scenario, backfill_complete=False)
        node = CheckInviteeNotAlreadyParticipantNode(
            case_id=_CASE_ID, invitee_id=_INVITEE_ID
        )
        result = bt_scenario.run(node, actor_id=_ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_returns_success_for_backfill_incomplete_resume_with_state(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Resume path (replication state exists, join_backfill_complete=False) → SUCCESS."""
        from vultron.core.models.replication_state import (
            VultronReplicationState,
        )

        _seed_case_with_participant(bt_scenario, backfill_complete=False)
        # Explicitly create an incomplete replication state record.
        state = VultronReplicationState(
            case_id=_CASE_ID,
            peer_id=_INVITEE_ID,
            join_backfill_target_index=5,
            join_backfill_last_sent_index=2,
            join_backfill_complete=False,
        )
        bt_scenario.dl.save(state)
        node = CheckInviteeNotAlreadyParticipantNode(
            case_id=_CASE_ID, invitee_id=_INVITEE_ID
        )
        result = bt_scenario.run(node, actor_id=_ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_returns_success_when_not_participant(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed_fresh_case(bt_scenario)
        node = CheckInviteeNotAlreadyParticipantNode(
            case_id=_CASE_ID, invitee_id=_INVITEE_ID
        )
        result = bt_scenario.run(node, actor_id=_ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_sets_invitee_already_participant_true_on_true_duplicate(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Guard writes invitee_already_participant=True before returning FAILURE."""
        import py_trees

        _seed_case_with_participant(bt_scenario, backfill_complete=True)
        node = CheckInviteeNotAlreadyParticipantNode(
            case_id=_CASE_ID, invitee_id=_INVITEE_ID
        )
        bt_scenario.run(node, actor_id=_ACTOR_ID)
        bb = py_trees.blackboard.Client(name="test-reader")
        bb.register_key(
            key="invitee_already_participant",
            access=py_trees.common.Access.READ,
        )
        assert bb.get("invitee_already_participant") is True

    def test_sets_invitee_already_participant_false_on_fresh(
        self, bt_scenario: BTTestScenario
    ) -> None:
        import py_trees

        _seed_fresh_case(bt_scenario)
        node = CheckInviteeNotAlreadyParticipantNode(
            case_id=_CASE_ID, invitee_id=_INVITEE_ID
        )
        bt_scenario.run(node, actor_id=_ACTOR_ID)
        bb = py_trees.blackboard.Client(name="test-reader-fresh")
        bb.register_key(
            key="invitee_already_participant",
            access=py_trees.common.Access.READ,
        )
        assert bb.get("invitee_already_participant") is False

    def test_returns_failure_when_case_not_found(
        self, bt_scenario: BTTestScenario
    ) -> None:
        node = CheckInviteeNotAlreadyParticipantNode(
            case_id="https://example.org/cases/nonexistent",
            invitee_id=_INVITEE_ID,
        )
        result = bt_scenario.run(node, actor_id=_ACTOR_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# CheckCaseStatusIdempotencyNode — AC-1
# ---------------------------------------------------------------------------


def _seed_case_with_status(
    bt_scenario: BTTestScenario,
) -> tuple[VulnerabilityCase, CaseStatus]:
    """Seed a case that already has a CaseStatus entry."""
    status = CaseStatus(context=_CASE_ID)
    case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
    case.case_statuses.append(status.id_)
    bt_scenario.dl.create(status)
    bt_scenario.dl.create(case)
    return case, status


class TestCheckCaseStatusIdempotencyNode:
    """CLP-13-001: guard FAILURE must not write a CaseLedgerEntry on duplicate fire."""

    def test_returns_failure_when_status_already_present(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _, status = _seed_case_with_status(bt_scenario)
        node = CheckCaseStatusIdempotencyNode(
            case_id=_CASE_ID, status_id=status.id_
        )
        result = bt_scenario.run(node, actor_id=_ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_no_ledger_entry_written_on_status_duplicate(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """AC-1: no CaseLedgerEntry is written when the status-idempotency guard fires."""
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        _, status = _seed_case_with_status(bt_scenario)
        node = CheckCaseStatusIdempotencyNode(
            case_id=_CASE_ID, status_id=status.id_
        )
        bt_scenario.run(node, actor_id=_ACTOR_ID)
        entries = [
            obj
            for obj in bt_scenario.dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry) and obj.case_id == _CASE_ID
        ]
        assert (
            entries == []
        ), f"Guard wrote {len(entries)} ledger entry/entries — CLP-13-001 violated"

    def test_sets_feedback_message_on_duplicate(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _, status = _seed_case_with_status(bt_scenario)
        node = CheckCaseStatusIdempotencyNode(
            case_id=_CASE_ID, status_id=status.id_
        )
        bt_scenario.run(node, actor_id=_ACTOR_ID)
        assert node.feedback_message == CASE_STATUS_ALREADY_PRESENT

    def test_returns_success_when_status_not_present(
        self, bt_scenario: BTTestScenario
    ) -> None:
        case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
        bt_scenario.dl.create(case)
        node = CheckCaseStatusIdempotencyNode(
            case_id=_CASE_ID, status_id="https://example.org/statuses/new"
        )
        result = bt_scenario.run(node, actor_id=_ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_returns_failure_when_case_not_found(
        self, bt_scenario: BTTestScenario
    ) -> None:
        node = CheckCaseStatusIdempotencyNode(
            case_id="https://example.org/cases/missing",
            status_id="https://example.org/statuses/s1",
        )
        result = bt_scenario.run(node, actor_id=_ACTOR_ID)
        assert result.status == Status.FAILURE
