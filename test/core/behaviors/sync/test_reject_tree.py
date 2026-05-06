#!/usr/bin/env python
"""Integration tests for RejectLogEntryReceivedBT."""

from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.reject_tree import (
    create_reject_log_entry_tree,
)
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_log import GENESIS_HASH, CaseLogEntry
from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases.triggers.sync import _to_persistable_entry
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import reject_log_entry_activity
from vultron.wire.as2.vocab.objects.case_log_entry import (
    CaseLogEntry as WireCaseLogEntry,
)

OWNER_ACTOR_ID = "https://example.org/actors/vendor"
PEER_ID = "https://example.org/actors/reporter"
CASE_ID = "https://example.org/cases/case-sync"


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def datalayer():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(datalayer):
    return BTBridge(datalayer=datalayer)


@pytest.fixture
def case_actor(datalayer):
    actor = VultronCaseActor(
        name="Case Actor",
        attributed_to=OWNER_ACTOR_ID,
        context=CASE_ID,
    )
    datalayer.create(actor)
    return actor


def _make_entry(log_index: int, prev_hash: str) -> VultronCaseLogEntry:
    return _to_persistable_entry(
        CaseLogEntry(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/log-{log_index}",
            event_type="test_event",
            payload_snapshot={"log_index": log_index},
            prev_log_hash=prev_hash,
        )
    )


def _make_event(
    entry: VultronCaseLogEntry, tail_hash: str
) -> RejectLogEntryReceivedEvent:
    wire_entry = WireCaseLogEntry.model_validate(entry.model_dump(mode="json"))
    activity = reject_log_entry_activity(
        entry=wire_entry,
        context=tail_hash,
        actor=PEER_ID,
        to=[OWNER_ACTOR_ID],
    )
    return cast(RejectLogEntryReceivedEvent, extract_event(activity))


def test_create_reject_log_entry_tree_returns_sequence():
    tree = create_reject_log_entry_tree()
    assert tree.name == "RejectLogEntryReceivedBT"
    assert len(tree.children) == 3


def test_reject_tree_updates_replication_state_and_replays_entries(
    bridge, datalayer, case_actor
):
    first_entry = _make_entry(0, GENESIS_HASH)
    second_entry = _make_entry(1, first_entry.entry_hash)
    datalayer.save(first_entry)
    datalayer.save(second_entry)
    event = _make_event(second_entry, tail_hash=first_entry.entry_hash)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=create_reject_log_entry_tree(),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    state_id = VultronReplicationState(
        case_id=CASE_ID,
        peer_id=PEER_ID,
        last_acknowledged_hash=first_entry.entry_hash,
    ).id_
    state = datalayer.read(state_id)
    assert state is not None
    assert state.last_acknowledged_hash == first_entry.entry_hash
    sync_port.send_announce_log_entry.assert_called_once()
    call_kwargs = sync_port.send_announce_log_entry.call_args.kwargs
    assert call_kwargs["entry"].id_ == second_entry.id_
    assert call_kwargs["actor_id"] == case_actor.id_
    assert call_kwargs["to"] == [PEER_ID]


def test_reject_tree_replays_all_entries_when_hash_not_found(
    bridge, datalayer, case_actor
):
    first_entry = _make_entry(0, GENESIS_HASH)
    second_entry = _make_entry(1, first_entry.entry_hash)
    datalayer.save(first_entry)
    datalayer.save(second_entry)
    event = _make_event(second_entry, tail_hash="deadbeef" * 8)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=create_reject_log_entry_tree(),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    assert sync_port.send_announce_log_entry.call_count == 2
