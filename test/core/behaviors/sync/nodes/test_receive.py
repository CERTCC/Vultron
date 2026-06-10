#!/usr/bin/env python
"""Unit tests for sync receive nodes."""

from unittest.mock import MagicMock

from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    PARTICIPANT_ACTOR_ID,
    _make_entry,
    _make_event,
)
from vultron.core.behaviors.sync.nodes import (
    CheckHashMatchesNode,
    CheckHashOrRejectOnMismatchNode,
    SendRejectLogEntryNode,
)
from vultron.core.models.case_log import GENESIS_HASH
from vultron.core.ports.sync_activity import SyncActivityPort


def test_check_hash_or_reject_on_mismatch_is_selector_with_condition_and_action():
    tree = CheckHashOrRejectOnMismatchNode(name="CheckHashOrRejectOnMismatch")
    assert tree.name == "CheckHashOrRejectOnMismatch"
    assert len(tree.children) == 2
    assert isinstance(tree.children[0], CheckHashMatchesNode)
    assert isinstance(tree.children[1], SendRejectLogEntryNode)


def test_check_hash_matches_node_succeeds_when_hash_matches(
    bridge, case_actor
):
    entry = _make_entry(0, GENESIS_HASH)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=CheckHashMatchesNode(name="CheckHashMatches"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
        tail_hash=GENESIS_HASH,
    )

    assert result.status == Status.SUCCESS


def test_send_reject_log_entry_node_sends_reject(bridge, case_actor):
    entry = _make_entry(1, "deadbeef" * 8)
    event = _make_event(entry, actor_id=case_actor.id_)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=SendRejectLogEntryNode(name="SendRejectLogEntry"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
        tail_hash=GENESIS_HASH,
        sync_port=sync_port,
    )

    assert result.status == Status.FAILURE
    sync_port.send_reject_log_entry.assert_called_once()


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


def test_check_hash_or_reject_on_mismatch_short_circuits_on_match(
    bridge, case_actor
):
    entry = _make_entry(0, GENESIS_HASH)
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

    assert result.status == Status.SUCCESS
    sync_port.send_reject_log_entry.assert_not_called()
