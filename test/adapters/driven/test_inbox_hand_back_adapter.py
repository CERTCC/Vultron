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

"""Tests for ``InboxHandBackAdapter`` (SYNC-14-009, ADR-0135)."""

import json
from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.inbox_hand_back_adapter import (
    InboxHandBackAdapter,
    hand_back_activity_id,
)
from vultron.adapters.inbox_staging import (
    InlineObjectStaging,
    hold_activity,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.ports.inbox_hand_back import InboxHandBackPort
from vultron.semantic_registry import extract_event
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

_CASE_MANAGER = "https://example.org/actors/case-manager"
_RECEIVER = "https://example.org/actors/receiver"
_CASE_ID = "https://example.org/cases/hand-back-adapter"


@pytest.fixture
def dl():
    db = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    yield db
    db.close()


@pytest.fixture
def entry() -> CaseLedgerEntry:
    record = HashChainLedgerRecord(
        case_id=_CASE_ID,
        log_index=3,
        object_id="https://example.org/activities/a3",
        semantic_type="test_event",
        payload_snapshot={"k": "v"},
        prev_log_hash="0" * 64,
    )
    return _to_persistable_entry(record)


def _adapter(dl: SqliteDataLayer) -> InboxHandBackAdapter:
    return InboxHandBackAdapter(dl, hold_activity)


def test_adapter_satisfies_the_port(dl):
    port: InboxHandBackPort = _adapter(dl)
    assert callable(port.hand_back_ledger_entry)


@pytest.mark.spec("SYNC-14-009")
@pytest.mark.spec("DL-06-006")
def test_hand_back_queues_an_announce_from_the_case_manager(dl, entry):
    """The Announce is held as a deferred delivery, never under its own id."""
    _adapter(dl).hand_back_ledger_entry(
        entry, case_manager_id=_CASE_MANAGER, receiving_actor_id=_RECEIVER
    )

    expected_id = hand_back_activity_id(_RECEIVER, entry.id_)
    assert dl.inbox_list() == [expected_id]
    assert dl.read(expected_id) is None
    held = dl.read(DeferredInboxActivity.build_id(expected_id))
    assert isinstance(held, DeferredInboxActivity)
    # Held as the body this delivery carries, as any delivery is, so its
    # replay is archived by intake (VM-08-002, ADR-0149).
    assert held.received_body is not None
    assert json.loads(held.received_body)["id"] == expected_id
    rebuilt = InlineObjectStaging(dl).rehydrate_held(expected_id)
    assert rebuilt is not None
    assert _as_id(getattr(rebuilt, "actor", None)) == _CASE_MANAGER
    assert getattr(rebuilt, "to", None) == [_RECEIVER]


@pytest.mark.spec("SYNC-13-002")
@pytest.mark.spec("SYNC-14-008")
def test_queued_announce_routes_like_any_ledger_entry_delivery(dl, entry):
    """Rebuilt from its record, as the inbox replay does, it routes to the
    announce use case with the entry inline, and the entry itself is never
    stored."""
    _adapter(dl).hand_back_ledger_entry(
        entry, case_manager_id=_CASE_MANAGER, receiving_actor_id=_RECEIVER
    )

    activity_id = dl.inbox_pop() or ""
    held = dl.read(DeferredInboxActivity.build_id(activity_id))
    assert isinstance(held, DeferredInboxActivity)
    activity = InlineObjectStaging(dl).rehydrate_deferred(activity_id)
    assert activity is not None
    # The replay carries the body the hand-back delivered (VM-08-002).
    assert activity.received_evidence_json == held.received_body
    event = cast(
        AnnounceLogEntryReceivedEvent,
        extract_event(cast(as_Activity, activity)),
    )
    assert event.semantic_type is MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY
    assert event.actor_id == _CASE_MANAGER
    assert event.log_entry == entry
    assert dl.read(entry.id_) is None


def test_handing_the_same_entry_back_twice_names_one_delivery(dl, entry):
    """Both hand-backs carry the same derived id (ID-04-004).

    The first is still held for its replay when the second arrives, so the
    second queues nothing: a replay must find the record it rebuilds from.
    """
    adapter = _adapter(dl)
    for _ in range(2):
        adapter.hand_back_ledger_entry(
            entry, case_manager_id=_CASE_MANAGER, receiving_actor_id=_RECEIVER
        )

    expected = hand_back_activity_id(_RECEIVER, entry.id_)
    assert dl.inbox_list() == [expected]


def test_a_hand_back_after_the_replay_is_queued_again(dl, entry):
    """Once the first is replayed, the same entry can be handed back again."""
    adapter = _adapter(dl)
    adapter.hand_back_ledger_entry(
        entry, case_manager_id=_CASE_MANAGER, receiving_actor_id=_RECEIVER
    )
    InlineObjectStaging(dl).rehydrate_deferred(dl.inbox_pop() or "")

    adapter.hand_back_ledger_entry(
        entry, case_manager_id=_CASE_MANAGER, receiving_actor_id=_RECEIVER
    )

    assert dl.inbox_list() == [hand_back_activity_id(_RECEIVER, entry.id_)]


def test_a_held_copy_left_unqueued_is_queued_by_the_next_hand_back(dl, entry):
    """An append that failed after the hold does not strand the entry."""
    adapter = _adapter(dl)
    adapter.hand_back_ledger_entry(
        entry, case_manager_id=_CASE_MANAGER, receiving_actor_id=_RECEIVER
    )
    expected = hand_back_activity_id(_RECEIVER, entry.id_)
    assert dl.inbox_pop() == expected, "precondition: queued once"

    adapter.hand_back_ledger_entry(
        entry, case_manager_id=_CASE_MANAGER, receiving_actor_id=_RECEIVER
    )

    assert dl.inbox_list() == [expected]
    assert InlineObjectStaging(dl).held(expected) is not None
