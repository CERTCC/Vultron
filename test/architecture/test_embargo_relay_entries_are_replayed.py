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

The full committed-versus-replayed inventory for every event type is #3814's.
"""

from typing import Any

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    _make_event,
    _to_persistable_entry,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    EMBARGO_ABANDONMENT_EVENT_TYPE,
    _ActivityEventNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.rsvp_deadline import INVITE_EXPIRED_EVENT_TYPE
from vultron.enums.roles import CVDRole

MANAGER = "https://example.org/actors/case-manager"
PROPOSER = "https://example.org/actors/proposer"
REPLICA = "https://example.org/actors/replica"
CASE_ID = "https://example.org/cases/relay-ratchet"
EMBARGO = {
    "type": "EmbargoEvent",
    "id": f"{CASE_ID}/embargo_events/e1",
    "context": CASE_ID,
}

_INVITE = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value

#: Entry shapes the CASE_MANAGER commits during the revision relay, each with
#: the snapshot that identifies it (EP-09-007).  The proposal and a relayed
#: Invite share one event type and differ by authorship.
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
    "Accept of an Invite": (
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value,
        {"type": "Accept", "actor": REPLICA, "object": {"object": EMBARGO}},
    ),
    "Reject of an Invite": (
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value,
        {"type": "Reject", "actor": REPLICA, "object": {"object": EMBARGO}},
    ),
    "the manager's abandonment of an Invite": (
        EMBARGO_ABANDONMENT_EVENT_TYPE,
        {"type": "Reject", "actor": MANAGER, "object": {"object": EMBARGO}},
    ),
    "teardown": (
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE.value,
        {"type": "Remove", "actor": MANAGER, "object": EMBARGO},
    ),
}

#: Embargo event types outside the revision relay, and who owns them.
OUTSIDE_THE_RELAY: dict[str, str] = {
    MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE.value: (
        "committed, not yet replayed — #3814 (ledger replay for every"
        " committed event type)"
    ),
    INVITE_EXPIRED_EVENT_TYPE: (
        "committed on a late Accept, replay owned by #3961 (RSVP deadline"
        " and invite expiry)"
    ),
    MessageSemantics.CREATE_EMBARGO_EVENT.value: "stores an object; commits nothing",
    MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE.value: (
        "no receiver-side state change; commits nothing"
    ),
}


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


def _effect_slot_conditions() -> list[_ActivityEventNode]:
    """The positive event conditions of the announce tree's effect slots.

    A condition under an ``Inverter`` is the slot's skip arm, not its match.
    """
    return [
        node
        for node in create_announce_log_entry_tree().iterate()
        if isinstance(node, _ActivityEventNode)
        and not isinstance(node.parent, py_trees.decorators.Inverter)
    ]


def _replica_store() -> SqliteDataLayer:
    """A replica holding the case, so the relay classifier sees the manager."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=REPLICA)
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=PROPOSER)
    manager = CaseParticipant(
        attributed_to=MANAGER,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(manager)
    case.actor_participant_index[MANAGER] = manager.id_
    dl.create(case)
    return dl


def _matching_slots(event_type: str, snapshot: dict[str, Any]) -> list[str]:
    dl = _replica_store()
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=f"urn:{event_type}",
            event_type=event_type,
            payload_snapshot={"context": CASE_ID, **snapshot},
            prev_log_hash="0" * 64,
        )
    )
    matched = []
    for condition in _effect_slot_conditions():
        py_trees.blackboard.Blackboard.storage.clear()
        result = BTBridge(datalayer=dl).execute_with_setup(
            tree=condition,
            actor_id=REPLICA,
            activity=_make_event(entry, actor_id=MANAGER),
        )
        if result.status == Status.SUCCESS:
            matched.append(condition.name)
    return matched


@pytest.mark.spec("RSH-08-004")
def test_every_embargo_semantic_is_classified():
    replayed = {event_type for event_type, _ in REPLAYED.values()}
    embargo_semantics = {
        member.value for member in MessageSemantics if "EMBARGO" in member.name
    }
    unclassified = embargo_semantics - replayed - set(OUTSIDE_THE_RELAY)
    assert not unclassified, (
        f"embargo event types neither replayed nor classified: {unclassified}"
    )
    assert not replayed & set(OUTSIDE_THE_RELAY)


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("EP-09-007")
@pytest.mark.parametrize("shape", sorted(REPLAYED))
def test_each_relay_entry_has_exactly_one_replay_slot(shape):
    event_type, snapshot = REPLAYED[shape]
    matched = _matching_slots(event_type, snapshot)
    assert len(matched) == 1, f"{shape}: {matched}"


@pytest.mark.spec("RSH-08-004")
@pytest.mark.parametrize("event_type", sorted(OUTSIDE_THE_RELAY))
def test_entries_outside_the_relay_have_no_slot_yet(event_type):
    """A slot here means the type is replayed: move it to ``REPLAYED``."""
    assert _matching_slots(event_type, {"actor": MANAGER}) == []
