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

"""Architecture ratchet: every committed ledger event type is replayed (RSH-08-004).

A participant replica takes case state from the CASE_MANAGER's ledger
(PCR-03-001, ADR-0108).  An ``event_type`` the CASE_MANAGER commits with no
effect slot in ``AnnounceLogEntryReceivedBT`` is stored and ignored, so the
replica silently stops following the case — and gating a received-side effect
behind the CASE_MANAGER role (RSH-08-003) before the slot exists blinds every
replica.

The committed set is derived from code (``_ledger_commit_inventory``), and each
member is classified here exactly once:

* :data:`REPLAYED` — matched by exactly one effect-slot condition of the
  announce tree, evaluated against a real entry rather than by slot name;
* :data:`NO_REPLICA_EFFECT` — the entry changes no state a replica holds, with
  the reason;
* :data:`KNOWN_UNREPLAYED` — a known violation of RSH-08-004: the entry has a
  replica effect that no slot applies yet.  Each row names the open issue that
  owns the fix; the set is exact and only shrinks (ARCH-18-001).  RSH-08-004
  also forbids gating a received-side effect of these types under RSH-08-003
  until its slot exists.

Both declared sets are matched by no slot, so the change that adds a replay
fails here until it moves the row to :data:`REPLAYED`.  The classification and
the committed set are held to equality (TB-10-002): a new committed type, or a
row for a type no longer committed, fails the ratchet.

:data:`AWAITING_COMMIT` lists types replayed ahead of the commit that will
produce them; it must stay disjoint from the committed set.

Every declared row carries a one-line reason.  The strict-``xfail`` goal test
passes — and so fails the build — once :data:`KNOWN_UNREPLAYED` empties, so
the change that closes the last gap deletes the set and the goal test instead
of leaving an empty ratchet behind.  The derivation is cached per process and
routed through ``_corpus`` (TB-13-001 through TB-13-003), which keeps each
test inside the TB-13-004 budget.
"""

from typing import Any

import pytest

from test.architecture._announce_slots import (
    MANAGER,
    PROPOSER,
    matching_slots,
)
from test.architecture._ledger_commit_inventory import (
    committed_event_types,
    explicit_event_types,
    received_commit_semantics,
)
from vultron.core.models.events.base import MessageSemantics as MS
from vultron.core.models.rsvp_deadline import (
    EMBARGO_REINVITE_EVENT_TYPE,
    HONOUR_LATE_ACCEPT_EVENT_TYPE,
    INVITE_EXPIRED_EVENT_TYPE,
    INVITE_EXPIRED_NOOP_EVENT_TYPE,
)

_EMBARGO = {"type": "EmbargoEvent", "id": "urn:uuid:embargo"}
_ABANDONED = f"{MS.REJECT_INVITE_TO_EMBARGO_ON_CASE.value}_abandoned"

#: Replayed event types and an entry snapshot that identifies each.  Only the
#: proposal-versus-relay split of ``invite_to_embargo_on_case`` depends on the
#: snapshot; ``test_embargo_relay_entries_are_replayed.py`` covers its shapes.
REPLAYED: dict[str, dict[str, Any]] = {
    event_type: {"actor": MANAGER, "object": _EMBARGO}
    for event_type in (
        MS.ACCEPT_CASE_OWNERSHIP_TRANSFER.value,
        MS.ACCEPT_INVITE_ACTOR_TO_CASE.value,
        MS.ACCEPT_INVITE_ACTOR_TO_FULL_CASE.value,
        MS.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE.value,
        MS.REJECT_INVITE_ACTOR_TO_FULL_CASE.value,
        MS.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value,
        MS.ACTIVATE_EMBARGO_ON_CASE.value,
        MS.ADD_CASE_PARTICIPANT_TO_CASE.value,
        MS.ADD_CASE_STATUS_TO_CASE.value,
        MS.ADD_NOTE_TO_CASE.value,
        MS.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT.value,
        MS.ADD_REPORT_TO_CASE.value,
        MS.CLOSE_CASE.value,
        MS.CLOSE_REPORT.value,
        MS.DEFER_CASE.value,
        MS.ENGAGE_CASE.value,
        MS.INVALIDATE_REPORT.value,
        MS.OFFER_CASE_OWNERSHIP_TRANSFER.value,
        MS.REJECT_EMBARGO_PROPOSAL_ON_CASE.value,
        MS.REJECT_INVITE_TO_EMBARGO_ON_CASE.value,
        MS.REMOVE_EMBARGO_EVENT_FROM_CASE.value,
        MS.REMOVE_CASE_PARTICIPANT_FROM_CASE.value,
        MS.REMOVE_NOTE_FROM_CASE.value,
        MS.VALIDATE_REPORT.value,
        EMBARGO_REINVITE_EVENT_TYPE,
        HONOUR_LATE_ACCEPT_EVENT_TYPE,
        INVITE_EXPIRED_EVENT_TYPE,
        INVITE_EXPIRED_NOOP_EVENT_TYPE,
        _ABANDONED,
    )
} | {
    MS.INVITE_TO_EMBARGO_ON_CASE.value: {
        "actor": PROPOSER,
        "object": _EMBARGO,
    },
}

_RECOMMENDATION = (
    "suggest-actor bookkeeping between the recommender, the CASE_MANAGER"
    " and the case owner (CM-16); no case state moves, and the member it may"
    " lead to arrives with accept_invite_actor_to_case"
)

#: Committed event types that change no state a replica holds.  A pinned
#: exemption set (ARCH-18-005): each row is a decision, not awaiting a fix.
# permanent: RSH-08-004 (the recorded no-replica-effect declarations)
NO_REPLICA_EFFECT: dict[str, str] = {
    "create_case": (
        "the genesis entry anchors the chain; a replica is seeded by the"
        " Create or Announce(VulnerabilityCase) it receives (CM-14-011,"
        " SYNC-15-002)"
    ),
    MS.INVITE_ACTOR_TO_FULL_CASE.value: (
        "an ask the CASE_MANAGER emits to a joined participant; it writes no"
        " case state, and the reply that judges the case carries the RM move"
        " (CM-11-010, CM-11-011)"
    ),
    MS.ACK_REPORT.value: (
        "Read(Offer) acknowledges receipt and moves no RM state (RK, ADR-0021)"
    ),
    "case_fully_closed": (
        "a marker; the transitions it summarises arrive as close_case and"
        " the CaseActor's add_participant_status_to_participant entry"
        " (CM-23-002, CM-23-005)"
    ),
    MS.OFFER_ACTOR_TO_CASE.value: _RECOMMENDATION,
    MS.OFFER_CASE_PARTICIPANT.value: _RECOMMENDATION,
    MS.ACCEPT_OFFER_CASE_PARTICIPANT.value: _RECOMMENDATION,
    MS.REJECT_OFFER_CASE_PARTICIPANT.value: _RECOMMENDATION,
    "accept_actor_recommendation": _RECOMMENDATION,
    "reject_actor_recommendation": _RECOMMENDATION,
    MS.OFFER_CASE_PARTICIPANT_ROLE.value: (
        "the CASE_MANAGER records the role-delegation offer as an assertion"
        " (ADR-0039, CLP-07-001), but an offer is a proposal, not the grant;"
        " it moves no case state, like Offer(CaseParticipant) (SE-08-003,"
        " #3764)"
    ),
}

#: Committed event types whose replica effect has no slot yet, and the open
#: issue that owns it.  Each reason names the issue.  A ratchet whose
#: terminal value is empty (ARCH-18-005).
# owner: #4294 #4295 #4404 (one per entry, named first in its reason)
KNOWN_UNREPLAYED: dict[str, str] = {
    MS.INVITE_ACTOR_TO_CASE.value: (
        "#4294 / #4295: the stub Invite creates the inert invitee's record"
        " (RM RECEIVED, PEC INVITED) on the CASE_MANAGER only (CM-11-006,"
        " ADR-0124)"
    ),
    MS.REJECT_INVITE_ACTOR_TO_CASE.value: (
        "#4294 / #4295: closes the inert invitee's record (RM CLOSED, PEC"
        " DECLINED) on the CASE_MANAGER only (CM-11-007, ADR-0124)"
    ),
    "accept_case_participant_role": (
        "#4404: the role grant the Accept records is applied by no received"
        " tree on any node; whether it should mutate participant roles is"
        " unspecified (#3764 fixed the offer half, SE-08-003)"
    ),
}

#: Replayed ahead of the commit that will produce them (event type → issue).
AWAITING_COMMIT: dict[str, str] = {}


def test_the_derivation_finds_both_commit_paths():
    """Guard against a vacuous pass: both scans find what they must."""
    received = received_commit_semantics()
    assert {
        MS.ADD_NOTE_TO_CASE.value,
        MS.ACTIVATE_EMBARGO_ON_CASE.value,
        MS.VALIDATE_REPORT.value,
    } <= received
    # A Create(VulnerabilityCase) is not ledgered as received (CLP-10-013).
    assert MS.CREATE_CASE.value not in received
    assert {
        "create_case",
        "case_fully_closed",
        INVITE_EXPIRED_EVENT_TYPE,
    } <= explicit_event_types()
    # A replay slot's own constant is compared, never committed, so defining
    # it must not make its type look committed: Add(Note) is committed only
    # on the receive side.
    assert MS.ADD_NOTE_TO_CASE.value not in explicit_event_types()


@pytest.mark.spec("RSH-08-004")
def test_every_committed_event_type_is_classified_exactly_once():
    """The classification equals the committed set (TB-10-002)."""
    tables = {
        "REPLAYED": set(REPLAYED) - set(AWAITING_COMMIT),
        "NO_REPLICA_EFFECT": set(NO_REPLICA_EFFECT),
        "KNOWN_UNREPLAYED": set(KNOWN_UNREPLAYED),
    }
    names = list(tables)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            assert not tables[first] & tables[second], (first, second)
    classified = set().union(*tables.values())
    committed = committed_event_types()
    assert committed - classified == set(), (
        "committed but unclassified — add a replay slot, or declare it"
    )
    assert classified - committed == set(), (
        "classified but no longer committed — remove the row"
    )


@pytest.mark.spec("RSH-08-004")
def test_types_replayed_ahead_of_their_commit_are_not_committed_yet():
    """When the commit lands, the row moves out of ``AWAITING_COMMIT``."""
    assert set(AWAITING_COMMIT) <= set(REPLAYED)
    assert not set(AWAITING_COMMIT) & committed_event_types()


@pytest.mark.spec("RSH-08-004")
@pytest.mark.parametrize("event_type", sorted(REPLAYED))
def test_each_replayed_type_has_exactly_one_slot(event_type):
    matched = matching_slots(event_type, REPLAYED[event_type])
    assert len(matched) == 1, f"{event_type}: {matched}"


@pytest.mark.spec("RSH-08-004")
@pytest.mark.parametrize(
    "event_type", sorted({**NO_REPLICA_EFFECT, **KNOWN_UNREPLAYED})
)
def test_declared_types_have_no_slot(event_type):
    """A slot here means the type is replayed: move it to ``REPLAYED``."""
    assert matching_slots(event_type, {"actor": MANAGER}) == []


@pytest.mark.parametrize(
    "event_type", sorted({**KNOWN_UNREPLAYED, **AWAITING_COMMIT})
)
def test_each_owned_gap_names_its_issue(event_type):
    reason = {**KNOWN_UNREPLAYED, **AWAITING_COMMIT}[event_type]
    assert reason.startswith("#"), reason


@pytest.mark.parametrize(
    ("table", "event_type"),
    [
        (name, event_type)
        for name, rows in (
            ("NO_REPLICA_EFFECT", NO_REPLICA_EFFECT),
            ("KNOWN_UNREPLAYED", KNOWN_UNREPLAYED),
            ("AWAITING_COMMIT", AWAITING_COMMIT),
        )
        for event_type in sorted(rows)
    ],
)
def test_each_declared_row_carries_a_one_line_reason(table, event_type):
    """A row is a recorded decision: a reason, on one line (RSH-08-004)."""
    reason = {
        "NO_REPLICA_EFFECT": NO_REPLICA_EFFECT,
        "KNOWN_UNREPLAYED": KNOWN_UNREPLAYED,
        "AWAITING_COMMIT": AWAITING_COMMIT,
    }[table][event_type]
    assert reason.strip(), f"{table}[{event_type!r}] has no reason"
    assert "\n" not in reason, f"{table}[{event_type!r}] spans lines"


@pytest.mark.spec("RSH-08-004")
@pytest.mark.xfail(
    strict=True,
    reason="goal: every committed type with a replica effect is replayed"
    " (#4294, #4295, #4404); when KNOWN_UNREPLAYED empties this passes and"
    " strict xfail fails the build — delete this test and the empty set",
)
def test_goal_no_committed_type_is_left_unreplayed():
    assert KNOWN_UNREPLAYED == {}
