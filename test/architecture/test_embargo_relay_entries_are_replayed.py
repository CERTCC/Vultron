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

"""Architecture ratchet: every embargo relay entry has a replay slot (RSH-08-004).

A participant replica takes embargo state from the CASE_MANAGER's ledger, never
from the activity that reached its inbox (RSH-08-003, ADR-0108).  An entry type
the CASE_MANAGER commits with no slot in ``AnnounceLogEntryReceivedBT`` is
stored and ignored, so the replica's state silently stops following the case
(#3892).  This ratchet pins the embargo rows of that inventory:

* every embargo ``MessageSemantics`` member is classified here as either
  replayed or outside the revision relay, so a new one cannot arrive
  unclassified;
* each replayed entry shape is matched by exactly one effect-slot condition
  of the announce tree, evaluated against a real entry rather than by name;
* each entry outside the relay is matched by none, so the issue that adds its
  replay is told to move it here.

The full committed-versus-replayed inventory for every semantic type is
``test_ledger_semantic_types_are_replayed.py``.
"""

from typing import Any

import pytest

from test.architecture._announce_slots import (
    CASE_ID,
    MANAGER,
    PROPOSER,
    REPLICA,
    matching_slots,
)
from vultron.core.models.events.base import MessageSemantics

EMBARGO = {
    "type": "EmbargoEvent",
    "id": f"{CASE_ID}/embargo_events/e1",
    "context": CASE_ID,
}

_INVITE = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value

#: Entry shapes the CASE_MANAGER commits during the revision relay, each with
#: the snapshot that identifies it (EP-09-007).  The proposal and a relayed
#: Invite share one semantic type and differ by authorship.
REPLAYED: dict[str, tuple[str, dict[str, Any]]] = {
    "proposal": (
        _INVITE,
        {"type": "Invite", "actor": PROPOSER, "object": EMBARGO},
    ),
    "relayed Invite": (
        _INVITE,
        {
            "type": "Invite",
            "actor": MANAGER,
            "attributedTo": PROPOSER,
            "to": [REPLICA],
            "object": EMBARGO,
        },
    ),
    "the manager's own proposal": (
        _INVITE,
        {"type": "Invite", "actor": MANAGER, "object": EMBARGO},
    ),
    "the manager's own terms, relayed": (
        _INVITE,
        {
            "type": "Invite",
            "actor": MANAGER,
            "attributedTo": MANAGER,
            "to": [REPLICA],
            "object": EMBARGO,
        },
    ),
    # A re-invite is a relay (ADR-0152): attributed to the embargo's
    # proposer, the manager itself for terms it made without a proposal.
    "the manager's re-invite to terms a participant proposed": (
        _INVITE,
        {
            "type": "Invite",
            "actor": MANAGER,
            "attributedTo": PROPOSER,
            "to": [REPLICA],
            "object": EMBARGO,
        },
    ),
    "the manager's re-invite to terms it made itself": (
        _INVITE,
        {
            "type": "Invite",
            "actor": MANAGER,
            "attributedTo": MANAGER,
            "to": [REPLICA],
            "object": EMBARGO,
        },
    ),
    "Accept of an Invite": (
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value,
        {"type": "Accept", "actor": REPLICA, "object": {"object": EMBARGO}},
    ),
    "Reject of an Invite": (
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value,
        {"type": "Reject", "actor": REPLICA, "object": {"object": EMBARGO}},
    ),
    "a signatory's withdrawal from the embargo in force": (
        MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE.value,
        {"type": "Leave", "actor": REPLICA, "object": EMBARGO},
    ),
    # The manager's abandonment (EMB-16-001, ADR-0152): its Reject shares the
    # participant's semantic type and is told apart by ``actor``.
    "the manager's Reject of a proposal it received": (
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value,
        {"type": "Reject", "actor": MANAGER, "object": {"object": EMBARGO}},
    ),
    "the manager's Undo of an Invite it sent": (
        MessageSemantics.UNDO_INVITE_TO_EMBARGO_ON_CASE.value,
        {"type": "Undo", "actor": MANAGER, "object": {"object": EMBARGO}},
    ),
    "teardown": (
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE.value,
        {"type": "Remove", "actor": MANAGER, "object": EMBARGO},
    ),
    "the owner's activation": (
        MessageSemantics.ACTIVATE_EMBARGO_ON_CASE.value,
        {"type": "Accept", "actor": PROPOSER, "object": EMBARGO},
    ),
    "the owner's rejection of a proposal": (
        MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE.value,
        {"type": "Reject", "actor": PROPOSER, "object": EMBARGO},
    ),
}

#: Shapes replayed against a replica whose register holds the embargo in
#: force: a re-invite names terms the case already has (EMB-17-003).
IN_FORCE: frozenset[str] = frozenset(
    {
        "the manager's re-invite to terms a participant proposed",
        "the manager's re-invite to terms it made itself",
    }
)

#: Embargo semantic types outside the revision relay, and who owns them.
OUTSIDE_THE_RELAY: dict[str, str] = {
    MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE.value: (
        "no receiver-side state change; commits nothing"
    ),
    MessageSemantics.CREATE_EMBARGO_EVENT.value: (
        "an embargo the case's creation wrote, stored by the CreatedEmbargo"
        " slot (test_rebuild_from_ledger.py)"
    ),
    MessageSemantics.CREATE_EMBARGO_CONSENT.value: (
        "a consent row, replayed by the consent-row slot"
        " (test_ledger_semantic_types_are_replayed.py)"
    ),
    MessageSemantics.UPDATE_EMBARGO_CONSENT.value: (
        "a consent row, replayed by the consent-row slot"
        " (test_ledger_semantic_types_are_replayed.py)"
    ),
}


@pytest.mark.spec("RSH-08-004")
def test_every_embargo_semantic_is_classified():
    replayed = {semantic_type for semantic_type, _ in REPLAYED.values()}
    embargo_semantics = {
        member.value for member in MessageSemantics if "EMBARGO" in member.name
    }
    unclassified = embargo_semantics - replayed - set(OUTSIDE_THE_RELAY)
    assert not unclassified, (
        f"embargo semantic types neither replayed nor classified: {unclassified}"
    )
    assert not replayed & set(OUTSIDE_THE_RELAY)


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("EP-09-007")
@pytest.mark.parametrize("shape", sorted(REPLAYED))
def test_each_relay_entry_has_exactly_one_replay_slot(shape):
    semantic_type, snapshot = REPLAYED[shape]
    matched = matching_slots(
        semantic_type,
        snapshot,
        active_embargo=EMBARGO["id"] if shape in IN_FORCE else None,
    )
    assert len(matched) == 1, f"{shape}: {matched}"


@pytest.mark.spec("EMB-17-003")
@pytest.mark.parametrize("shape", sorted(IN_FORCE))
def test_a_reinvite_is_applied_by_the_relay_slot(shape):
    """It proposes nothing, so it never reaches the proposal slot."""
    semantic_type, snapshot = REPLAYED[shape]
    assert matching_slots(
        semantic_type, snapshot, active_embargo=EMBARGO["id"]
    ) == ["IsEmbargoInviteRelayEvent"]


@pytest.mark.spec("EMB-16-001")
@pytest.mark.spec("SE-03-004")
@pytest.mark.parametrize(
    ("shape", "slot"),
    [
        (
            "the manager's Reject of a proposal it received",
            "IsEmbargoAbandonmentEvent",
        ),
        ("Reject of an Invite", "IsEmbargoRejectionEvent"),
    ],
)
def test_the_managers_reject_and_a_participants_take_different_slots(
    shape, slot
):
    """One semantic type, told apart after routing by ``actor`` (ADR-0152)."""
    assert matching_slots(*REPLAYED[shape]) == [slot]
