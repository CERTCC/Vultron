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

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.inbox_hand_back_adapter import (
    InboxHandBackAdapter,
    hand_back_activity_id,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.ports.inbox_hand_back import InboxHandBackPort
from vultron.semantic_registry import extract_event
from vultron.wire.as2.rehydration import rehydrate
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
        event_type="test_event",
        payload_snapshot={"k": "v"},
        prev_log_hash="0" * 64,
    )
    return CaseLedgerEntry(
        case_id=record.case_id,
        log_index=record.log_index,
        term=record.term,
        log_object_id=record.object_id,
        event_type=record.event_type,
        payload_snapshot=dict(record.payload_snapshot),
        prev_log_hash=record.prev_log_hash,
        entry_hash=record.entry_hash,
    )


def test_adapter_satisfies_the_port(dl):
    port: InboxHandBackPort = InboxHandBackAdapter(dl)
    assert callable(port.hand_back_ledger_entry)


@pytest.mark.spec("SYNC-14-009")
def test_hand_back_queues_an_announce_from_the_case_manager(dl, entry):
    InboxHandBackAdapter(dl).hand_back_ledger_entry(
        entry, case_manager_id=_CASE_MANAGER, receiving_actor_id=_RECEIVER
    )

    expected_id = hand_back_activity_id(_RECEIVER, entry.id_)
    assert dl.inbox_list() == [expected_id]
    stored = dl.read(expected_id)
    assert stored is not None
    assert _as_id(getattr(stored, "actor", None)) == _CASE_MANAGER
    assert getattr(stored, "to", None) == [_RECEIVER]


@pytest.mark.spec("SYNC-13-002")
@pytest.mark.spec("SYNC-14-008")
def test_queued_announce_routes_like_any_ledger_entry_delivery(dl, entry):
    """Re-read by id, as the inbox loop does, it routes to the announce use
    case with the entry inline, and the entry itself is never stored."""
    InboxHandBackAdapter(dl).hand_back_ledger_entry(
        entry, case_manager_id=_CASE_MANAGER, receiving_actor_id=_RECEIVER
    )

    activity = rehydrate(dl.inbox_pop() or "", dl=dl)
    event = cast(
        AnnounceLogEntryReceivedEvent,
        extract_event(cast(as_Activity, activity)),
    )
    assert event.semantic_type is MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY
    assert event.actor_id == _CASE_MANAGER
    assert event.log_entry == entry
    assert dl.read(entry.id_) is None


def test_handing_the_same_entry_back_twice_names_one_delivery(dl, entry):
    adapter = InboxHandBackAdapter(dl)
    for _ in range(2):
        adapter.hand_back_ledger_entry(
            entry, case_manager_id=_CASE_MANAGER, receiving_actor_id=_RECEIVER
        )

    assert set(dl.inbox_list()) == {
        hand_back_activity_id(_RECEIVER, entry.id_)
    }
