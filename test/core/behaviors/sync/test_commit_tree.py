#!/usr/bin/env python
"""Integration tests for CommitLogEntryBT."""

from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models.case import VultronCase
from vultron.core.models.case_log import GENESIS_HASH, CaseLogEntry
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases.triggers.sync import _to_persistable_entry

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
def case_obj(datalayer):
    case = VultronCase(
        id_=CASE_ID,
        attributed_to=OWNER_ACTOR_ID,
        actor_participant_index={
            OWNER_ACTOR_ID: f"{CASE_ID}/participants/vendor",
            PEER_ID: f"{CASE_ID}/participants/reporter",
        },
    )
    datalayer.save(case)
    return case


def _make_entry(log_index: int, prev_hash: str):
    return _to_persistable_entry(
        CaseLogEntry(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/log-{log_index}",
            event_type="test_event",
            payload_snapshot={},
            prev_log_hash=prev_hash,
        )
    )


def test_create_commit_log_entry_tree_returns_sequence():
    tree = create_commit_log_entry_tree(
        case_id=CASE_ID,
        object_id="https://example.org/activities/act-1",
        event_type="case_created",
    )
    assert tree.name == "CommitLogEntryBT"
    assert len(tree.children) == 4


def test_commit_tree_persists_entry_and_fans_out(bridge, datalayer, case_obj):
    sync_port = MagicMock(spec=SyncActivityPort)
    tree = create_commit_log_entry_tree(
        case_id=CASE_ID,
        object_id="https://example.org/activities/act-1",
        event_type="case_created",
    )

    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=OWNER_ACTOR_ID,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    entries = list(datalayer.list_objects("CaseLogEntry"))
    assert len(entries) == 1
    assert entries[0].log_index == 0
    assert entries[0].prev_log_hash == GENESIS_HASH
    sync_port.send_announce_log_entry.assert_called_once()
    call_kwargs = sync_port.send_announce_log_entry.call_args.kwargs
    assert call_kwargs["to"] == [PEER_ID]


def test_commit_tree_uses_existing_tail_hash(bridge, datalayer, case_obj):
    first_entry = _make_entry(0, GENESIS_HASH)
    datalayer.save(first_entry)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=create_commit_log_entry_tree(
            case_id=CASE_ID,
            object_id="https://example.org/activities/act-2",
            event_type="case_updated",
        ),
        actor_id=OWNER_ACTOR_ID,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    entries = sorted(
        datalayer.list_objects("CaseLogEntry"),
        key=lambda entry: entry.log_index,
    )
    assert len(entries) == 2
    assert entries[1].log_index == 1
    assert entries[1].prev_log_hash == first_entry.entry_hash
