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
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import reject_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)

OWNER_ACTOR_ID = "https://example.org/actors/vendor"
PEER_ID = "https://example.org/actors/reporter"
CASE_ID = "https://example.org/cases/case-sync"

_ZERO_HASH: str = "0" * 64  # arbitrary prev_log_hash for test chains


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


def _make_entry(
    log_index: int, prev_hash: str = _ZERO_HASH
) -> VultronCaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/log-{log_index}",
            event_type="test_event",
            payload_snapshot={"log_index": log_index},
            prev_log_hash=prev_hash,
        )
    )


def _make_event(
    entry: VultronCaseLedgerEntry, tail_hash: str
) -> RejectLogEntryReceivedEvent:
    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
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
    assert len(tree.children) == 4


def test_reject_tree_updates_replication_state_and_replays_entries(
    bridge, datalayer, case_actor
):
    first_entry = _make_entry(0)
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
    first_entry = _make_entry(0)
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


def test_genesis_reject_queues_announce_vulnerability_case(
    datalayer, case_actor
):
    """When last_accepted_hash='', AnnounceVulnerabilityCase is sent before
    entry replay so the peer can anchor its hash chain (SYNC-15-002).
    """
    from vultron.core.ports.trigger_activity import TriggerActivityPort

    entry = _make_entry(0)
    datalayer.save(entry)
    event = _make_event(entry, tail_hash="")
    sync_port = MagicMock(spec=SyncActivityPort)
    trigger_activity = MagicMock(spec=TriggerActivityPort)
    trigger_activity.announce_vulnerability_case.return_value = (
        "https://example.org/activities/announce-case-1"
    )

    bridge = BTBridge(
        datalayer=datalayer,
        sync_port=sync_port,
        trigger_activity=trigger_activity,
    )
    result = bridge.execute_with_setup(
        tree=create_reject_log_entry_tree(),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    trigger_activity.announce_vulnerability_case.assert_called_once()
    call_kwargs = trigger_activity.announce_vulnerability_case.call_args.kwargs
    assert call_kwargs["case_id"] == CASE_ID
    assert call_kwargs["to"] == [PEER_ID]


def test_genesis_reject_without_trigger_port_still_succeeds(
    bridge, datalayer, case_actor
):
    """Missing trigger port is a WARNING, not a FAILURE — replay continues
    (SYNC-15-002 is best-effort; replay remains the backstop).
    """
    entry = _make_entry(0)
    datalayer.save(entry)
    event = _make_event(entry, tail_hash="")
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=create_reject_log_entry_tree(),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS


def test_non_genesis_reject_skips_announce_vulnerability_case(
    datalayer, case_actor
):
    """When last_accepted_hash is non-empty the node is a no-op — the peer
    already has the case and does not need re-seeding (SYNC-15-002).
    """
    from vultron.core.ports.trigger_activity import TriggerActivityPort

    first_entry = _make_entry(0)
    second_entry = _make_entry(1, first_entry.entry_hash)
    datalayer.save(first_entry)
    datalayer.save(second_entry)
    event = _make_event(second_entry, tail_hash=first_entry.entry_hash)
    sync_port = MagicMock(spec=SyncActivityPort)
    trigger_activity = MagicMock(spec=TriggerActivityPort)

    bridge = BTBridge(
        datalayer=datalayer,
        sync_port=sync_port,
        trigger_activity=trigger_activity,
    )
    result = bridge.execute_with_setup(
        tree=create_reject_log_entry_tree(),
        actor_id=OWNER_ACTOR_ID,
        activity=event,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    trigger_activity.announce_vulnerability_case.assert_not_called()


# ---------------------------------------------------------------------------
# Reject/replay amplification guard (SYNC-15-003)
# ---------------------------------------------------------------------------


def test_repeated_reject_at_same_hash_does_not_replay_unboundedly(
    bridge, datalayer, case_actor
):
    """A peer stuck at the same ``last_accepted_hash`` must not trigger an
    unbounded full-ledger replay on every Reject.

    Regression guard for the reject/replay amplification loop: a late-joining
    participant that cannot anchor its hash chain re-Rejects each replayed
    entry, and each Reject previously re-replayed the *entire* ledger.  With a
    25-entry ledger this produced thousands of Announce activities, starving
    the container until unrelated DataLayer reads timed out.

    The first Reject at a given hash SHOULD replay; subsequent Rejects at the
    *same* hash MUST NOT replay again, because nothing has changed — the peer
    has made no progress, so re-sending the same entries cannot help.
    """
    entries = [_make_entry(0)]
    for index in range(1, 25):
        entries.append(_make_entry(index, entries[-1].entry_hash))
    for entry in entries:
        datalayer.save(entry)

    sync_port = MagicMock(spec=SyncActivityPort)

    # The peer is stuck: it never advances past entry 0.
    stuck_hash = entries[0].entry_hash
    for _ in range(10):
        py_trees.blackboard.Blackboard.storage.clear()
        result = bridge.execute_with_setup(
            tree=create_reject_log_entry_tree(),
            actor_id=OWNER_ACTOR_ID,
            activity=_make_event(entries[-1], tail_hash=stuck_hash),
            sync_port=sync_port,
        )
        assert result.status == Status.SUCCESS

    # Without a guard this is 10 rounds × 24 missing entries = 240 announces.
    # With the guard only the first round replays.
    assert sync_port.send_announce_log_entry.call_count == len(entries) - 1


def test_reject_at_advanced_hash_replays_again(bridge, datalayer, case_actor):
    """The guard must not wedge a peer that *is* making progress.

    When a peer's ``last_accepted_hash`` advances between Rejects, the replay
    MUST fire again for the newly-missing suffix.
    """
    entries = [_make_entry(0)]
    for index in range(1, 4):
        entries.append(_make_entry(index, entries[-1].entry_hash))
    for entry in entries:
        datalayer.save(entry)

    sync_port = MagicMock(spec=SyncActivityPort)

    for stuck_at in range(3):
        py_trees.blackboard.Blackboard.storage.clear()
        result = bridge.execute_with_setup(
            tree=create_reject_log_entry_tree(),
            actor_id=OWNER_ACTOR_ID,
            activity=_make_event(
                entries[-1], tail_hash=entries[stuck_at].entry_hash
            ),
            sync_port=sync_port,
        )
        assert result.status == Status.SUCCESS

    # Progress at index 0, 1, 2 → 3 + 2 + 1 = 6 replayed entries.
    assert sync_port.send_announce_log_entry.call_count == 6
