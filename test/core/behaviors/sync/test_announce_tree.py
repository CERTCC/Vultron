#!/usr/bin/env python
"""Integration tests for AnnounceLogEntryReceivedBT."""

from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_log import GENESIS_HASH, CaseLogEntry
from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases.triggers.sync import _to_persistable_entry
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.vocab.objects.case_log_entry import (
    CaseLogEntry as WireCaseLogEntry,
)

OWNER_ACTOR_ID = "https://example.org/actors/vendor"
PARTICIPANT_ACTOR_ID = "https://example.org/actors/reporter"
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
    entry: VultronCaseLogEntry, actor_id: str
) -> AnnounceLogEntryReceivedEvent:
    wire_entry = WireCaseLogEntry.model_validate(entry.model_dump(mode="json"))
    activity = announce_log_entry_activity(entry=wire_entry, actor=actor_id)
    return cast(AnnounceLogEntryReceivedEvent, extract_event(activity))


def test_create_announce_log_entry_tree_returns_selector():
    tree = create_announce_log_entry_tree()
    assert tree.name == "AnnounceLogEntryReceivedBT"
    assert len(tree.children) == 2


def test_participant_persists_valid_entry(bridge, datalayer, case_actor):
    entry = _make_entry(0, GENESIS_HASH)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
        sync_port=MagicMock(spec=SyncActivityPort),
    )

    assert result.status == Status.SUCCESS
    assert datalayer.read(entry.id_) is not None


def test_case_actor_round_trip_logs_delivery_without_repersisting(
    bridge, datalayer, case_actor
):
    entry = _make_entry(0, GENESIS_HASH)
    datalayer.save(entry)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS
    entries = list(datalayer.list_objects("CaseLogEntry"))
    assert len(entries) == 1


def test_case_actor_spoofed_sender_fails(bridge, datalayer, case_actor):
    entry = _make_entry(0, GENESIS_HASH)
    event = _make_event(
        entry, actor_id="https://example.org/actors/attacker-service"
    )

    result = bridge.execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.FAILURE
    assert datalayer.read(entry.id_) is None


def test_hash_mismatch_sends_reject_and_does_not_store(
    bridge, datalayer, case_actor
):
    first_entry = _make_entry(0, GENESIS_HASH)
    datalayer.save(first_entry)
    bad_entry = _make_entry(1, "badbadbadbadbad0" * 4)
    event = _make_event(bad_entry, actor_id=case_actor.id_)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
        sync_port=sync_port,
    )

    assert result.status == Status.FAILURE
    assert datalayer.read(bad_entry.id_) is None
    sync_port.send_reject_log_entry.assert_called_once()
