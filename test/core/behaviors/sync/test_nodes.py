#!/usr/bin/env python
"""Unit tests for sync BT nodes."""

from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.nodes import (
    CheckHashOrRejectOnMismatchNode,
    CheckIsOwnCaseActorNode,
    CreateLogEntryNode,
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


def test_check_is_own_case_actor_succeeds_for_case_owner(bridge, case_actor):
    entry = _make_entry(0, GENESIS_HASH)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=CheckIsOwnCaseActorNode(name="CheckIsOwnCaseActor"),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.SUCCESS


def test_check_hash_or_reject_on_mismatch_sends_reject(bridge, case_actor):
    entry = _make_entry(1, "deadbeef" * 8)
    event = _make_event(entry, actor_id=case_actor.id_)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=CheckHashOrRejectOnMismatchNode(
            name="CheckHashOrRejectOnMismatch"
        ),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
        tail_hash=GENESIS_HASH,
        sync_port=sync_port,
    )

    assert result.status == Status.FAILURE
    sync_port.send_reject_log_entry.assert_called_once()


def test_create_log_entry_node_writes_log_entry_to_blackboard(bridge):
    result = bridge.execute_with_setup(
        tree=CreateLogEntryNode(
            case_id=CASE_ID,
            object_id="https://example.org/activities/act-1",
            event_type="case_created",
            name="CreateLogEntry",
        ),
        actor_id=OWNER_ACTOR_ID,
        tail_hash=GENESIS_HASH,
        tail_index=-1,
    )

    assert result.status == Status.SUCCESS
    blackboard = py_trees.blackboard.Client(name="assert-log-entry")
    blackboard.register_key(
        key="log_entry", access=py_trees.common.Access.READ
    )
    assert blackboard.log_entry.case_id == CASE_ID
    assert blackboard.log_entry.log_index == 0
