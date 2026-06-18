#!/usr/bin/env python
"""Unit tests for sync replay and fan-out nodes."""

from typing import cast
from unittest.mock import MagicMock

import py_trees
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_entry,
)
from vultron.core.behaviors.sync.nodes import (
    CollectAndSortCaseLedgerEntriesNode,
    CollectLogEntryRecipientsNode,
    FanOutLogEntryNode,
    FindDivergenceIndexNode,
    ReplayMissingEntriesNode,
    SendLogEntryToEachNode,
    SendMissingEntriesNode,
)
from vultron.core.models.case import VultronCase
from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import reject_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    CaseLedgerEntry as WireCaseLedgerEntry,
)

_ZERO_HASH: str = "0" * 64  # arbitrary hash for test chains


def _make_reject_event(
    *, tail_hash: str, entry_log_index: int = 1
) -> RejectLogEntryReceivedEvent:
    prev_hash = _ZERO_HASH if entry_log_index == 0 else "deadbeef" * 8
    entry = _make_entry(entry_log_index, prev_hash)
    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    activity = reject_log_entry_activity(
        entry=wire_entry,
        context=tail_hash,
        actor=PARTICIPANT_ACTOR_ID,
        to=[OWNER_ACTOR_ID],
    )
    return cast(RejectLogEntryReceivedEvent, extract_event(activity))


def test_replay_missing_entries_node_is_sequence_with_named_leaf_nodes():
    tree = ReplayMissingEntriesNode(name="ReplayMissingEntries")
    assert isinstance(tree, py_trees.composites.Sequence)
    assert len(tree.children) == 3
    assert isinstance(tree.children[0], CollectAndSortCaseLedgerEntriesNode)
    assert isinstance(tree.children[1], FindDivergenceIndexNode)
    assert isinstance(tree.children[2], SendMissingEntriesNode)


def test_send_missing_entries_node_replays_entries_after_divergence(
    bridge, case_actor
):
    first_entry = _make_entry(0)
    second_entry = _make_entry(1, first_entry.entry_hash)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=SendMissingEntriesNode(name="SendMissingEntries"),
        actor_id=OWNER_ACTOR_ID,
        sync_port=sync_port,
        case_actor_id=case_actor.id_,
        replay_entry=second_entry,
        replay_peer_id=PARTICIPANT_ACTOR_ID,
        replay_case_ledger_entries=[first_entry, second_entry],
        replay_from_index=0,
    )

    assert result.status == Status.SUCCESS
    sync_port.send_announce_log_entry.assert_called_once()
    kwargs = sync_port.send_announce_log_entry.call_args.kwargs
    assert kwargs["entry"].id_ == second_entry.id_
    assert kwargs["actor_id"] == case_actor.id_
    assert kwargs["to"] == [PARTICIPANT_ACTOR_ID]


def test_collect_and_find_replay_context_writes_blackboard(bridge, datalayer):
    first_entry = _make_entry(0)
    second_entry = _make_entry(1, first_entry.entry_hash)
    datalayer.save(second_entry)
    datalayer.save(first_entry)
    event = _make_reject_event(tail_hash=first_entry.entry_hash)

    collect_result = bridge.execute_with_setup(
        tree=CollectAndSortCaseLedgerEntriesNode(
            name="CollectAndSortCaseLedgerEntries"
        ),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
    )

    assert collect_result.status == Status.SUCCESS
    replay_entries = py_trees.blackboard.Blackboard.storage.get(
        "/replay_case_ledger_entries"
    )
    assert replay_entries is not None
    assert [entry.log_index for entry in replay_entries] == [0, 1]
    assert (
        py_trees.blackboard.Blackboard.storage.get("/replay_peer_id")
        == PARTICIPANT_ACTOR_ID
    )

    find_result = bridge.execute_with_setup(
        tree=FindDivergenceIndexNode(name="FindDivergenceIndex"),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
        replay_case_ledger_entries=replay_entries,
    )

    assert find_result.status == Status.SUCCESS
    assert (
        py_trees.blackboard.Blackboard.storage.get("/replay_from_index") == 0
    )


def test_fanout_log_entry_node_is_sequence_with_named_leaf_nodes():
    tree = FanOutLogEntryNode(case_id=CASE_ID, name="FanOutLogEntry")
    assert isinstance(tree, py_trees.composites.Sequence)
    assert len(tree.children) == 2
    assert isinstance(tree.children[0], CollectLogEntryRecipientsNode)
    assert isinstance(tree.children[1], SendLogEntryToEachNode)


def test_replay_missing_entries_node_replays_from_divergence(
    bridge, datalayer, case_actor
):
    first_entry = _make_entry(0)
    second_entry = _make_entry(1, first_entry.entry_hash)
    datalayer.save(first_entry)
    datalayer.save(second_entry)
    event = _make_reject_event(tail_hash=first_entry.entry_hash)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=ReplayMissingEntriesNode(name="ReplayMissingEntries"),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
        case_actor_id=case_actor.id_,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    sync_port.send_announce_log_entry.assert_called_once()
    kwargs = sync_port.send_announce_log_entry.call_args.kwargs
    assert kwargs["entry"].id_ == second_entry.id_
    assert kwargs["actor_id"] == case_actor.id_
    assert kwargs["to"] == [PARTICIPANT_ACTOR_ID]


def test_fanout_log_entry_node_sends_to_case_addressees(bridge, datalayer):
    case_obj = VultronCase(
        id_=CASE_ID,
        attributed_to=OWNER_ACTOR_ID,
        actor_participant_index={
            OWNER_ACTOR_ID: f"{CASE_ID}/participants/vendor",
            PARTICIPANT_ACTOR_ID: f"{CASE_ID}/participants/reporter",
        },
    )
    datalayer.save(case_obj)
    entry = _make_entry(0)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=FanOutLogEntryNode(case_id=CASE_ID, name="FanOutLogEntry"),
        actor_id=OWNER_ACTOR_ID,
        log_entry=entry,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    sync_port.send_announce_log_entry.assert_called_once()
    kwargs = sync_port.send_announce_log_entry.call_args.kwargs
    assert kwargs["entry"].id_ == entry.id_
    assert kwargs["actor_id"] == OWNER_ACTOR_ID
    assert kwargs["to"] == [PARTICIPANT_ACTOR_ID]
