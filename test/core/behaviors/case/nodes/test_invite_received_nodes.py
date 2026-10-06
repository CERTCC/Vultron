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


def _anchor_node(
    invitee_id: str = INVITEE_ID,
    case_actor_id: str = CASE_ACTOR_ID,
    case_id: str = CASE_ID,
) -> RecordInviteTrustAnchorNode:
    return RecordInviteTrustAnchorNode(
        case_id=case_id,
        invitee_id=invitee_id,
        case_actor_id=case_actor_id,
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
    """AC-3: a second Invite naming a different CaseActor is REFUSED; anchor unchanged."""

    def test_ac3_conflicting_second_invite_returns_failure(self):
        """A second run with a different case_actor_id returns FAILURE."""
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        # First run writes the anchor.
        scenario.run(_anchor_node(case_actor_id=CASE_ACTOR_ID))
        # Second run with a different CaseActor — conflict.
        result = scenario.run(_anchor_node(case_actor_id=OTHER_CASE_ACTOR_ID))
        scenario.assert_failure(result)

    def test_ac3_conflicting_second_invite_is_not_internal_error(self):
        """The conflict FAILURE is a protocol outcome, not a wiring error."""
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.run(_anchor_node(case_actor_id=CASE_ACTOR_ID))
        result = scenario.run(_anchor_node(case_actor_id=OTHER_CASE_ACTOR_ID))
        assert result.internal_error is False

    def test_ac3_conflicting_second_invite_logs_warning(self, caplog):
        """The conflict is logged at WARNING naming both CaseActor ids."""
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.run(_anchor_node(case_actor_id=CASE_ACTOR_ID))
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
        """Existing anchor is unchanged after a conflicting second Invite."""
        scenario = BTTestScenario(actor_id=INVITEE_ID)
        scenario.run(_anchor_node(case_actor_id=CASE_ACTOR_ID))
        scenario.run(_anchor_node(case_actor_id=OTHER_CASE_ACTOR_ID))
        record = scenario.dl.read(VultronPendingCaseInbox.build_id(CASE_ID))
        assert isinstance(record, VultronPendingCaseInbox)
        assert record.case_actor_id == CASE_ACTOR_ID, (
            "Original anchor MUST NOT be overwritten by a conflicting second Invite"
        )


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
