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

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.case_owner import CASE_OWNER_ID
from vultron.core.behaviors.case.nodes import (
    CheckInviteeNotAlreadyParticipantNode,
)
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.behaviors.status.nodes.case_status import (
    CASE_STATUS_ALREADY_PRESENT,
    CheckCaseStatusIdempotencyNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus

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
    joined: bool = True,
    removed: bool = False,
    paused: bool = False,
) -> VulnerabilityCase:
    """Seed a case whose roster already holds the invitee's record.

    ``paused`` also stores an embargo-pause replication state for it, which
    the guard must not read (CM-17-012).
    """
    from vultron.core.models.replication_state import VultronReplicationState

    participant = CaseParticipant(
        id_=f"{_CASE_ID}/participants/invitee",
        attributed_to=_INVITEE_ID,
        context=_CASE_ID,
        joined=joined,
    )
    if removed:
        participant.record_removal(f"{_CASE_ID}/removals/1")
    case = VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_=_CASE_ID,
        name="Test Case",
    )
    case.add_participant(participant)
    bt_scenario.dl.create(participant)
    bt_scenario.dl.create(case)
    if paused:
        bt_scenario.dl.save(
            VultronReplicationState(
                case_id=_CASE_ID,
                peer_id=_INVITEE_ID,
                embargo_paused_from_index=0,
            )
        )
    return case


def _seed_fresh_case(bt_scenario: BTTestScenario) -> VulnerabilityCase:
    """Seed a case with no participants."""
    case = VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, id_=_CASE_ID, name="Test Case"
    )
    bt_scenario.dl.create(case)
    return case


def _run_guard(bt_scenario: BTTestScenario) -> Status:
    node = CheckInviteeNotAlreadyParticipantNode(
        case_id=_CASE_ID, invitee_id=_INVITEE_ID
    )
    return bt_scenario.run(node, actor_id=_ACTOR_ID).status


@pytest.mark.spec("CM-17-005")
@pytest.mark.spec("CM-17-012")
class TestCheckInviteeNotAlreadyParticipantNode:
    """The duplicate test reads the participant record alone (CM-17-012)."""

    @pytest.mark.parametrize(
        "seed",
        [
            {"joined": True},
            {"joined": True, "paused": True},
            {"joined": True, "removed": True},
            {"joined": False, "removed": True},
        ],
        ids=[
            "joined-no-replication-state",
            "joined-embargo-paused",
            "removed",
            "removed-before-joining",
        ],
    )
    def test_a_joined_or_removed_invitee_is_a_duplicate(
        self, bt_scenario: BTTestScenario, seed: dict[str, bool]
    ) -> None:
        """FAILURE with no ledger entry (CLP-13-001), whatever its state."""
        _seed_case_with_participant(bt_scenario, **seed)

        assert _run_guard(bt_scenario) == Status.FAILURE
        assert bt_scenario.dl.list_objects("CaseLedgerEntry") == [], (
            "the guard wrote a ledger entry — CLP-13-001 violated"
        )

    def test_an_inert_invitee_proceeds(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """An inert record's first Accept joins it (CM-17-004, CM-11-006)."""
        _seed_case_with_participant(bt_scenario, joined=False)
        assert _run_guard(bt_scenario) == Status.SUCCESS

    def test_an_invitee_with_no_record_proceeds_to_the_refusal(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """No record is not a duplicate: CM-11-021 refuses it next."""
        _seed_fresh_case(bt_scenario)
        assert _run_guard(bt_scenario) == Status.SUCCESS

    @pytest.mark.spec("BT-17-003")
    @pytest.mark.parametrize(
        ("joined", "expected_status"),
        [(False, Status.SUCCESS), (True, Status.FAILURE)],
        ids=["inert-writes-the-case", "duplicate-clears-it"],
    )
    def test_invitee_case_is_the_case_or_cleared(
        self,
        bt_scenario: BTTestScenario,
        joined: bool,
        expected_status: Status,
    ) -> None:
        """SUCCESS hands the consent nodes the case; a duplicate clears it."""
        case = _seed_case_with_participant(bt_scenario, joined=joined)
        captured: list[object] = []

        class _Probe(py_trees.behaviour.Behaviour):
            def update(self) -> Status:
                captured.append(
                    py_trees.blackboard.Blackboard.storage.get("/invitee_case")
                )
                return Status.SUCCESS

        guard = CheckInviteeNotAlreadyParticipantNode(
            case_id=_CASE_ID, invitee_id=_INVITEE_ID
        )
        tree = py_trees.composites.Selector(
            name="GuardOrProbe",
            memory=False,
            children=[
                py_trees.composites.Sequence(
                    name="GuardThenProbe",
                    memory=False,
                    children=[guard, _Probe(name="AfterSuccess")],
                ),
                _Probe(name="AfterFailure"),
            ],
        )

        # A stale case from an earlier run must not survive a duplicate.
        bt_scenario.run(tree, actor_id=_ACTOR_ID, invitee_case="stale")

        assert guard.status == expected_status
        if expected_status == Status.SUCCESS:
            assert captured == [case]
        else:
            assert captured == [None]

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
    case = VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, id_=_CASE_ID, name="Test Case"
    )
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
        assert entries == [], (
            f"Guard wrote {len(entries)} ledger entry/entries — CLP-13-001 violated"
        )

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
        case = VulnerabilityCase(
            attributed_to=CASE_OWNER_ID, id_=_CASE_ID, name="Test Case"
        )
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
