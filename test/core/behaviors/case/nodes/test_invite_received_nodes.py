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

"""Unit tests for ``RecordInviteTrustAnchorNode`` (PCR-03-004, issue #4185).

Covers the three trust rules added in #4185:

- AC-1: invitee_id must equal the receiving actor; mismatched → FAILURE, no record.
- AC-2: anchor binds to the Invite's ``actor`` id (case_actor_id), not the
  transport-level delivering sender.
- AC-3: a second invocation for the same case naming a different CaseActor →
  FAILURE at WARNING level; existing anchor unchanged.

Also covers: first-write semantics, idempotent re-run, and the
``case_actor_id=None`` fill-in path.
"""

import logging

import pytest

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.nodes.invite_received import (
    FixInviteTrustAnchorNode,
    RecordInviteTrustAnchorNode,
)
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox

CASE_ID = "https://example.org/cases/anchor-tests-1"
INVITEE_ID = "https://example.org/actors/invitee"
CASE_ACTOR_ID = "https://example.org/actors/case-manager"
OTHER_CASE_ACTOR_ID = "https://example.org/actors/other-case-manager"
TRANSPORT_SENDER_ID = (
    "https://example.org/actors/relay"  # different from actor field
)


def _invite_id(case_actor_id: str, n: int = 1) -> str:
    """The id of the *n*-th stub Invite *case_actor_id* sends."""
    return f"{case_actor_id}/invites/{n}"


def _anchor_node(
    invitee_id: str = INVITEE_ID,
    case_actor_id: str = CASE_ACTOR_ID,
    case_id: str = CASE_ID,
    invite_id: str | None = None,
) -> RecordInviteTrustAnchorNode:
    return RecordInviteTrustAnchorNode(
        case_id=case_id,
        invitee_id=invitee_id,
        case_actor_id=case_actor_id,
        invite_id=invite_id or _invite_id(case_actor_id),
    )


def _accept(scenario: BTTestScenario, case_actor_id: str = CASE_ACTOR_ID):
    """The invitee accepts *case_actor_id*'s first Invite."""
    return scenario.run(
        FixInviteTrustAnchorNode(invite_id=_invite_id(case_actor_id))
    )


@pytest.mark.spec("PCR-03-004")
class TestRecordInviteTrustAnchorNodeAC1:
    """AC-1: invitee_id must equal the receiving actor."""

    def test_ac1_invitee_matches_receiver_writes_anchor(self):
        """When invitee == receiving actor the anchor is written (happy path)."""
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        result = scenario.run(_anchor_node(invitee_id=INVITEE_ID))
        scenario.assert_success(result)
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.case_actor_id == CASE_ACTOR_ID

    def test_ac1_invitee_differs_from_receiver_returns_failure(self):
        """When invitee != receiving actor the node returns FAILURE, no record."""
        different_receiver = "https://example.org/actors/vendor"
        # The node is parameterised with INVITEE_ID but runs as different_receiver.
        scenario = BTTestScenario(actor_id=different_receiver)
        result = scenario.run(_anchor_node(invitee_id=INVITEE_ID))
        scenario.assert_failure(result)
        assert (
            scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID)) is None
        )

    def test_ac1_failure_is_not_an_internal_error(self):
        """The misaddressed-invitee FAILURE is a protocol outcome, not a wiring error."""
        different_receiver = "https://example.org/actors/vendor"
        scenario = BTTestScenario(actor_id=different_receiver)
        result = scenario.run(_anchor_node(invitee_id=INVITEE_ID))
        assert result.internal_error is False

    def test_ac1_failure_logs_at_warning(self, caplog):
        """A misaddressed Invite is logged at WARNING (PCR-03-004 path b)."""
        different_receiver = "https://example.org/actors/vendor"
        scenario = BTTestScenario(actor_id=different_receiver)
        with caplog.at_level(logging.WARNING):
            scenario.run(_anchor_node(invitee_id=INVITEE_ID))
        warnings = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and INVITEE_ID in r.getMessage()
        ]
        assert warnings, "Expected a WARNING naming the mismatched invitee id"

    def test_ac1_failure_no_record_written(self):
        """No VultronPendingCaseInbox is created when AC-1 fails."""
        different_receiver = "https://example.org/actors/vendor"
        scenario = BTTestScenario(actor_id=different_receiver)
        scenario.run(_anchor_node(invitee_id=INVITEE_ID))
        assert (
            scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID)) is None
        )

    def test_ac1_trailing_slash_tolerance(self):
        """Invitee and receiver that differ only by a trailing slash are the same."""
        scenario = BTTestScenario(actor_id=INVITEE_ID + "/")
        result = scenario.run(_anchor_node(invitee_id=INVITEE_ID))
        scenario.assert_success(result)
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)


@pytest.mark.spec("PCR-03-004")
class TestRecordInviteTrustAnchorNodeAC2:
    """AC-2: anchor binds to the Invite's actor id; transport sender ignored."""

    def test_ac2_anchor_uses_case_actor_id_not_transport_sender(self):
        """The node stores ``case_actor_id`` faithfully as the anchor's actor id.

        AC-2's transport-vs-actor guarantee is architectural: the tree factory
        passes ``inviter_id = request.actor_id`` (the Invite's own ``actor``
        field) as ``case_actor_id`` — the transport sender never enters the
        call chain.  The node-level contract being tested here is that the
        node stores exactly the ``case_actor_id`` it receives, unchanged.
        End-to-end verification is in ``test_invite_invitee_path_stores_trust_anchor``
        at the use-case level.
        """
        # The node receives case_actor_id = CASE_ACTOR_ID (the Invite's actor).
        # TRANSPORT_SENDER_ID is the relay/transport sender — it never appears here.
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        result = scenario.run(
            _anchor_node(
                invitee_id=INVITEE_ID,
                case_actor_id=CASE_ACTOR_ID,
            )
        )
        scenario.assert_success(result)
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.case_actor_id == CASE_ACTOR_ID
        assert record.case_actor_id != TRANSPORT_SENDER_ID


@pytest.mark.spec("PCR-03-004")
class TestRecordInviteTrustAnchorNodeAC3:
    """AC-3: once the anchoring Invite is accepted, a conflicting one is REFUSED."""

    @staticmethod
    def _accepted_scenario() -> BTTestScenario:
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.assert_success(
            scenario.run(_anchor_node(case_actor_id=CASE_ACTOR_ID))
        )
        scenario.assert_success(_accept(scenario))
        return scenario

    def test_ac3_conflicting_second_invite_returns_failure(self):
        """A conflicting Invite after the Accept returns FAILURE."""
        scenario = self._accepted_scenario()
        result = scenario.run(_anchor_node(case_actor_id=OTHER_CASE_ACTOR_ID))
        scenario.assert_failure(result)

    def test_ac3_conflicting_second_invite_is_not_internal_error(self):
        """The conflict FAILURE is a protocol outcome, not a wiring error."""
        scenario = self._accepted_scenario()
        result = scenario.run(_anchor_node(case_actor_id=OTHER_CASE_ACTOR_ID))
        assert result.internal_error is False

    def test_ac3_conflicting_second_invite_logs_warning(self, caplog):
        """The conflict is logged at WARNING naming both CaseActor ids."""
        scenario = self._accepted_scenario()
        with caplog.at_level(logging.WARNING):
            scenario.run(_anchor_node(case_actor_id=OTHER_CASE_ACTOR_ID))
        warnings = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING
            and CASE_ACTOR_ID in r.getMessage()
            and OTHER_CASE_ACTOR_ID in r.getMessage()
        ]
        assert warnings, (
            "Expected a WARNING naming both CaseActor ids (existing and conflicting)"
        )

    def test_ac3_conflicting_second_invite_anchor_unchanged(self):
        """The accepted anchor is unchanged after a conflicting Invite."""
        scenario = self._accepted_scenario()
        scenario.run(_anchor_node(case_actor_id=OTHER_CASE_ACTOR_ID))
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.case_actor_id == CASE_ACTOR_ID, (
            "An accepted anchor MUST NOT be overwritten by a conflicting Invite"
        )
        assert record.invite_accepted


@pytest.mark.spec("PCR-03-004")
class TestRecordInviteTrustAnchorNodeReplacesAnUnacceptedAnchor:
    """A later Invite replaces an anchor whose Invite no Accept followed.

    A forged stub Invite naming its own sender must not lock out the real
    CASE_MANAGER's Invite until the bootstrap; forgery itself remains a risk
    until signatures (#2841).
    """

    def test_a_later_invite_replaces_the_anchor(self):
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.run(_anchor_node(case_actor_id=OTHER_CASE_ACTOR_ID))
        scenario.assert_success(
            scenario.run(_anchor_node(case_actor_id=CASE_ACTOR_ID))
        )
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.case_actor_id == CASE_ACTOR_ID
        assert record.anchor_invite_id == _invite_id(CASE_ACTOR_ID)
        assert record.invite_anchored
        assert not record.invite_accepted

    def test_the_replacement_is_logged_at_info_with_both_senders(self, caplog):
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.run(_anchor_node(case_actor_id=OTHER_CASE_ACTOR_ID))
        with caplog.at_level(logging.INFO):
            scenario.run(_anchor_node(case_actor_id=CASE_ACTOR_ID))
        assert any(
            r.levelno == logging.INFO
            and "replaced" in r.getMessage()
            and CASE_ACTOR_ID in r.getMessage()
            and OTHER_CASE_ACTOR_ID in r.getMessage()
            for r in caplog.records
        )

    def test_the_accept_of_a_superseded_invite_fixes_nothing(self):
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.run(_anchor_node(case_actor_id=OTHER_CASE_ACTOR_ID))
        scenario.run(_anchor_node(case_actor_id=CASE_ACTOR_ID))
        scenario.assert_success(_accept(scenario, OTHER_CASE_ACTOR_ID))
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.case_actor_id == CASE_ACTOR_ID
        assert not record.invite_accepted


@pytest.mark.spec("PCR-03-004")
class TestFixInviteTrustAnchorNode:
    """The invitee's Accept fixes the anchor its Invite set."""

    def test_the_accept_fixes_the_anchor(self, caplog):
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.run(_anchor_node())
        with caplog.at_level(logging.INFO):
            scenario.assert_success(_accept(scenario))
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.invite_accepted
        assert any(
            r.levelno == logging.INFO and "fixed" in r.getMessage()
            for r in caplog.records
        )

    def test_an_accept_with_no_anchor_succeeds_and_writes_nothing(self):
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.assert_success(_accept(scenario))
        assert (
            scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID)) is None
        )

    def test_a_repeated_accept_is_idempotent(self):
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.run(_anchor_node())
        _accept(scenario)
        scenario.assert_success(_accept(scenario))
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.invite_accepted

    def test_a_same_sender_reinvite_moves_the_awaited_invite(self):
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.run(_anchor_node())
        second = _invite_id(CASE_ACTOR_ID, 2)
        scenario.assert_success(scenario.run(_anchor_node(invite_id=second)))
        scenario.assert_success(
            scenario.run(FixInviteTrustAnchorNode(invite_id=second))
        )
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.anchor_invite_id == second
        assert record.invite_accepted


@pytest.mark.spec("PCR-03-004")
class TestRecordInviteTrustAnchorNodeIdempotency:
    """Idempotent re-run and pre-bootstrap fill-in paths."""

    def test_duplicate_same_actor_is_idempotent(self):
        """Re-running with the same case_actor_id is a SUCCESS (idempotent)."""
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        result_first = scenario.run(_anchor_node(case_actor_id=CASE_ACTOR_ID))
        result_second = scenario.run(_anchor_node(case_actor_id=CASE_ACTOR_ID))
        scenario.assert_success(result_first)
        scenario.assert_success(result_second)
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.case_actor_id == CASE_ACTOR_ID

    def test_fill_in_replaces_none_case_actor(self):
        """A pre-bootstrap record with case_actor_id=None is filled in."""
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        # Seed a record with no actor yet (as the pre-bootstrap queue creates).
        scenario.dl.create(
            VultronPendingCaseInbox(case_id=CASE_ID, case_actor_id=None)
        )
        result = scenario.run(_anchor_node(case_actor_id=CASE_ACTOR_ID))
        scenario.assert_success(result)
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.case_actor_id == CASE_ACTOR_ID


@pytest.mark.spec("PCR-03-004", "CBT-03-003")
class TestRecordInviteTrustAnchorNodeMarksTheAnchor:
    """Every anchor the node writes or confirms is ``invite_anchored``.

    The pre-bootstrap queue shares the record, and its expiry keeps only an
    anchored one (#4915).
    """

    def test_a_new_anchor_is_marked(self):
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.assert_success(scenario.run(_anchor_node()))
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.invite_anchored

    def test_a_filled_in_anchor_is_marked(self):
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.dl.create(
            VultronPendingCaseInbox(case_id=CASE_ID, case_actor_id=None)
        )
        scenario.assert_success(scenario.run(_anchor_node()))
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.invite_anchored

    def test_a_queue_record_from_the_same_sender_is_marked(self, caplog):
        """The queue recorded the sender first; the Invite confirms it."""
        caplog.set_level(logging.INFO)
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.dl.create(
            VultronPendingCaseInbox(
                case_id=CASE_ID,
                activity_ids=["https://example.org/activities/a1"],
                case_actor_id=CASE_ACTOR_ID,
            )
        )
        scenario.assert_success(scenario.run(_anchor_node()))
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.invite_anchored
        assert record.activity_ids == ["https://example.org/activities/a1"]
        assert any(
            r.levelno == logging.INFO
            and "confirmed as trust anchor" in r.message
            for r in caplog.records
        ), "promoting the queue's sender to the anchor is a state change"

    def test_a_conflicting_invite_leaves_the_anchor(self):
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.dl.create(
            VultronPendingCaseInbox(
                case_id=CASE_ID,
                case_actor_id=OTHER_CASE_ACTOR_ID,
                invite_anchored=True,
                anchor_invite_id=_invite_id(OTHER_CASE_ACTOR_ID),
                invite_accepted=True,
            )
        )
        scenario.assert_failure(scenario.run(_anchor_node()))
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.case_actor_id == OTHER_CASE_ACTOR_ID


@pytest.mark.spec("PCR-03-004", "CBT-03-004")
class TestRecordInviteTrustAnchorNodeOverQueueRecordedSender:
    """A sender the queue recorded is a replay target, not an anchor (#4931).

    The first deferred activity from any actor records its sender
    (CBT-03-004).  A stub Invite naming another CaseActor is not a second
    Invite, so it anchors trust in place of that sender.
    """

    def _scenario_with_queued_sender(self) -> BTTestScenario:
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.dl.create(
            VultronPendingCaseInbox(
                case_id=CASE_ID,
                activity_ids=["https://example.org/activities/a1"],
                case_actor_id=OTHER_CASE_ACTOR_ID,
            )
        )
        return scenario

    def test_stub_invite_anchors_over_queue_recorded_sender(self):
        scenario = self._scenario_with_queued_sender()
        scenario.assert_success(scenario.run(_anchor_node()))
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.case_actor_id == CASE_ACTOR_ID
        assert record.invite_anchored

    def test_the_queued_activities_are_kept(self):
        scenario = self._scenario_with_queued_sender()
        scenario.run(_anchor_node())
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.activity_ids == ["https://example.org/activities/a1"]
