#!/usr/bin/env python
"""Unit tests for sync receive nodes."""

from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    PARTICIPANT_ACTOR_ID,
    _make_entry,
    _make_event,
)
from test.support.inbox_replay import archive_event
from vultron.core.behaviors.sync.nodes import (
    BufferOutOfOrderEntryNode,
    CheckHashMatchesNode,
    CheckHashOrRejectOnMismatchNode,
    SendRejectLogEntryNode,
)
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.services.held_ledger_announces import held_ledger_announces

_ZERO_HASH: str = "0" * 64  # arbitrary hash for test chains


@pytest.mark.spec("SYNC-03-001")
def test_check_hash_or_reject_on_mismatch_is_selector_with_condition_and_action():
    tree = CheckHashOrRejectOnMismatchNode(name="CheckHashOrRejectOnMismatch")
    assert tree.name == "CheckHashOrRejectOnMismatch"
    assert len(tree.children) == 2
    assert isinstance(tree.children[0], CheckHashMatchesNode)
    # Second child buffers a forward gap (so it is not dropped) and then
    # always sends the reject as the loss backstop (issue #1556).
    buffer_and_reject = tree.children[1]
    assert isinstance(buffer_and_reject, py_trees.composites.Sequence)
    buffer_decorator, reject_node = buffer_and_reject.children
    assert isinstance(buffer_decorator, py_trees.decorators.FailureIsSuccess)
    assert isinstance(buffer_decorator.children[0], BufferOutOfOrderEntryNode)
    assert isinstance(reject_node, SendRejectLogEntryNode)


@pytest.mark.spec("SYNC-03-001")
def test_check_hash_matches_node_succeeds_when_hash_matches(
    bridge, case_actor
):
    entry = _make_entry(0)
    event = _make_event(entry, actor_id=case_actor.id_)

    result = bridge.execute_with_setup(
        tree=CheckHashMatchesNode(name="CheckHashMatches"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
        tail_hash=_ZERO_HASH,
    )

    assert result.status == Status.SUCCESS


@pytest.mark.spec("SYNC-03-001")
def test_send_reject_log_entry_node_sends_reject(bridge, case_actor):
    entry = _make_entry(1, "deadbeef" * 8)
    event = _make_event(entry, actor_id=case_actor.id_)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=SendRejectLogEntryNode(name="SendRejectLogEntry"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
        tail_hash=_ZERO_HASH,
        sync_port=sync_port,
    )

    assert result.status == Status.FAILURE
    sync_port.send_reject_log_entry.assert_called_once()


@pytest.mark.spec("SYNC-03-001")
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
        tail_hash=_ZERO_HASH,
        sync_port=sync_port,
    )

    assert result.status == Status.FAILURE
    sync_port.send_reject_log_entry.assert_called_once()


@pytest.mark.spec("SYNC-03-001")
def test_check_hash_or_reject_on_mismatch_short_circuits_on_match(
    bridge, case_actor
):
    entry = _make_entry(0)
    event = _make_event(entry, actor_id=case_actor.id_)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=CheckHashOrRejectOnMismatchNode(
            name="CheckHashOrRejectOnMismatch"
        ),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
        tail_hash=_ZERO_HASH,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    sync_port.send_reject_log_entry.assert_not_called()


class TestBufferOutOfOrderEntryNode:
    """Direct unit tests for BufferOutOfOrderEntryNode.update() branch paths."""

    @pytest.mark.spec("SYNC-14-001")
    @pytest.mark.spec("SYNC-14-002")
    def test_holds_the_announce_of_a_genuine_forward_gap(
        self, bridge, datalayer, case_actor
    ):
        """An entry two indices ahead of the tail is a forward gap: its
        received Announce is held → SUCCESS."""
        # tail_index=0; entry at log_index=2 is a forward gap (> tail+1).
        entry = _make_entry(2, "deadbeef" * 8)
        event = _make_event(entry, actor_id=case_actor.id_)
        archive_event(datalayer, event)

        result = bridge.execute_with_setup(
            tree=BufferOutOfOrderEntryNode(name="BufferOutOfOrderEntry"),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            tail_index=0,
        )

        assert result.status == Status.SUCCESS
        [held] = held_ledger_announces(datalayer, entry.case_id)
        assert held.activity_id == event.activity_id

    @pytest.mark.spec("SYNC-14-001")
    def test_does_not_hold_at_tail_entry(self, bridge, datalayer, case_actor):
        """An entry at log_index == tail_index + 1 is not a forward gap — FAILURE."""
        # tail_index=0; entry at log_index=1 is the expected next, not a gap.
        entry = _make_entry(1, "deadbeef" * 8)
        event = _make_event(entry, actor_id=case_actor.id_)
        archive_event(datalayer, event)

        result = bridge.execute_with_setup(
            tree=BufferOutOfOrderEntryNode(name="BufferOutOfOrderEntry"),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
            tail_index=0,
        )

        assert result.status == Status.FAILURE
        assert held_ledger_announces(datalayer, entry.case_id) == []

    @pytest.mark.spec("SYNC-14-005")
    def test_returns_failure_when_no_tail_index(
        self, bridge, datalayer, case_actor
    ):
        """Without a tail index on the blackboard there is no gap to measure."""
        entry = _make_entry(5, "deadbeef" * 8)
        event = _make_event(entry, actor_id=case_actor.id_)

        result = bridge.execute_with_setup(
            tree=BufferOutOfOrderEntryNode(name="BufferOutOfOrderEntry"),
            actor_id=PARTICIPANT_ACTOR_ID,
            activity=event,
        )

        assert result.status == Status.FAILURE
        assert held_ledger_announces(datalayer, entry.case_id) == []
