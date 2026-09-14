#!/usr/bin/env python
"""Integration tests for CommitLogEntryBT."""

from unittest.mock import MagicMock

import py_trees
import pytest

from vultron.core.models._helpers import _now_utc
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes import (
    CreateLogEntryNode,
    DeclineForeignLedgerCommitNode,
)
from vultron.core.models.case import VultronCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry

_ZERO_HASH: str = "0" * 64  # arbitrary hash for test chains

OWNER_ACTOR_ID = "https://example.org/actors/vendor"
PEER_ID = "https://example.org/actors/reporter"
CASE_ID = "https://example.org/cases/case-sync"


def _canonical_note_snapshot(actor_id: str, note_id: str) -> dict[str, object]:
    return {
        "type": "Add",
        "actor": actor_id,
        # CLP-07-011: recorded snapshots carry the asserter's claimed timestamp.
        "published": _now_utc().isoformat(),
        "object": {
            "type": "Note",
            "id": note_id,
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def datalayer():
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=OWNER_ACTOR_ID,
    )


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
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=f"https://example.org/activities/log-{log_index}",
            event_type="test_event",
            payload_snapshot={},
            prev_log_hash=prev_hash,
        )
    )


@pytest.mark.spec("CLP-02-001")
@pytest.mark.spec("BT-05-006")
def test_create_commit_log_entry_tree_guards_the_mint():
    """The four commit nodes sit behind the ledger-authority guard (ADR-0073)."""
    tree = create_commit_log_entry_tree(
        case_id=CASE_ID,
        object_id="https://example.org/activities/act-1",
        event_type="case_created",
    )
    assert tree.name == "CommitLogEntryBT"
    guard, mint = tree.children
    assert isinstance(guard, DeclineForeignLedgerCommitNode)
    assert mint.name == "MintAndFanOutLogEntry"
    assert len(mint.children) == 4


@pytest.mark.spec("CLP-02-001")
@pytest.mark.spec("SYNC-01-002")
@pytest.mark.spec("SYNC-01-003")
@pytest.mark.spec("SYNC-02-001")
@pytest.mark.spec("SYNC-02-003")
@pytest.mark.spec("CLP-08-004")
def test_commit_tree_persists_entry_and_fans_out(bridge, datalayer, case_obj):
    sync_port = MagicMock(spec=SyncActivityPort)
    tree = create_commit_log_entry_tree(
        case_id=CASE_ID,
        object_id="https://example.org/activities/act-1",
        event_type="case_created",
        payload_snapshot=_canonical_note_snapshot(
            PEER_ID, "https://example.org/notes/note-1"
        ),
    )

    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=OWNER_ACTOR_ID,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    entries = list(datalayer.list_objects("CaseLedgerEntry"))
    assert len(entries) == 1
    assert entries[0].log_index == 0
    assert entries[0].prev_log_hash == case_obj.genesis_hash
    assert len(entries[0].prev_log_hash) == 64
    sync_port.send_announce_log_entry.assert_called_once()
    call_kwargs = sync_port.send_announce_log_entry.call_args.kwargs
    assert call_kwargs["to"] == [PEER_ID]


@pytest.mark.spec("SYNC-01-002")
@pytest.mark.spec("SYNC-01-003")
def test_commit_tree_uses_existing_tail_hash(bridge, datalayer, case_obj):
    first_entry = _make_entry(0, case_obj.genesis_hash)
    datalayer.save(first_entry)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=create_commit_log_entry_tree(
            case_id=CASE_ID,
            object_id="https://example.org/activities/act-2",
            event_type="case_updated",
            payload_snapshot=_canonical_note_snapshot(
                PEER_ID, "https://example.org/notes/note-2"
            ),
        ),
        actor_id=OWNER_ACTOR_ID,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    entries = sorted(
        datalayer.list_objects("CaseLedgerEntry"),
        key=lambda entry: entry.log_index,
    )
    assert len(entries) == 2
    assert entries[1].log_index == 1
    assert entries[1].prev_log_hash == first_entry.entry_hash


@pytest.mark.spec("SYNC-03-003")
@pytest.mark.spec("CLP-07-002")
def test_commit_tree_reuses_equivalent_entry(bridge, datalayer, case_obj):
    sync_port = MagicMock(spec=SyncActivityPort)
    tree = create_commit_log_entry_tree(
        case_id=CASE_ID,
        object_id="https://example.org/activities/act-3",
        event_type="case_updated",
        payload_snapshot=_canonical_note_snapshot(
            PEER_ID, "https://example.org/notes/note-3"
        ),
    )

    first = bridge.execute_with_setup(
        tree=tree,
        actor_id=OWNER_ACTOR_ID,
        sync_port=sync_port,
    )
    second = bridge.execute_with_setup(
        tree=create_commit_log_entry_tree(
            case_id=CASE_ID,
            object_id="https://example.org/activities/act-3",
            event_type="case_updated",
            payload_snapshot=_canonical_note_snapshot(
                PEER_ID, "https://example.org/notes/note-3"
            ),
        ),
        actor_id=OWNER_ACTOR_ID,
        sync_port=sync_port,
    )

    assert first.status == Status.SUCCESS
    assert second.status == Status.SUCCESS
    entries = [
        entry
        for entry in datalayer.list_objects("CaseLedgerEntry")
        if entry.case_id == CASE_ID
    ]
    assert len(entries) == 1


@pytest.mark.spec("CLP-07-011")
def test_create_commit_log_entry_tree_default_payload_snapshot_is_empty_dict():
    """Omitting payload_snapshot passes an empty dict through to CreateLogEntryNode."""
    tree = create_commit_log_entry_tree(
        case_id=CASE_ID,
        object_id="https://example.org/activities/act-cs21",
        event_type="case_created",
    )
    create_node = next(
        c for c in tree.iterate() if isinstance(c, CreateLogEntryNode)
    )
    assert create_node.payload_snapshot == {}
    assert create_node.payload_snapshot is not None


@pytest.mark.spec("BT-05-006")
@pytest.mark.spec("CLP-08-005")
@pytest.mark.spec("CLP-10-001")
def test_commit_tree_declines_to_mint_for_a_foreign_ledger(
    bridge, datalayer, case_obj
):
    """A delegated emit against a remote CaseActor must not claim an index.

    This is the post-handoff shape from #2626: the case owner emits as the
    case's CaseActor, which lives on another container, so ``BTBridge`` hands
    the tree the *owner's* store (BT-05-005).  Minting here would fork the
    canonical chain — the real CaseActor mints its own entry at the same index
    from the ``cc:`` copy — so the commit is declined and the entry is left to
    arrive by replication (CLP-10-001).
    """
    sync_port = MagicMock(spec=SyncActivityPort)
    tree = create_commit_log_entry_tree(
        case_id=CASE_ID,
        object_id="https://example.org/activities/act-remote",
        event_type="invite_actor_to_case",
        payload_snapshot=_canonical_note_snapshot(
            PEER_ID, "https://example.org/notes/note-remote"
        ),
    )

    result = bridge.execute_with_setup(
        tree=tree,
        actor_id="https://other.example.net/actors/case-actor",
        sync_port=sync_port,
    )

    # SUCCESS, because declining *is* handling it — every caller reads a
    # non-SUCCESS commit as a hard failure.
    assert result.status == Status.SUCCESS
    assert list(datalayer.list_objects("CaseLedgerEntry")) == []
    sync_port.send_announce_log_entry.assert_not_called()


@pytest.mark.spec("BT-05-006")
@pytest.mark.parametrize(
    "actor_id,expected",
    [
        # This store's own actor, and a CaseActor co-hosted with it: the bridge
        # can hand the tree that actor's store, so the mint is this store's to
        # make and the guard stands aside.
        (OWNER_ACTOR_ID, Status.FAILURE),
        ("https://example.org/actors/case-actor", Status.FAILURE),
        # Another container's CaseActor — the post-handoff shape.
        ("https://other.example.net/actors/case-actor", Status.SUCCESS),
    ],
)
def test_decline_foreign_ledger_commit_only_declines_foreign(
    bridge, actor_id, expected
):
    """FAILURE means "go commit"; SUCCESS means "declined, not ours to mint"."""
    result = bridge.execute_with_setup(
        tree=DeclineForeignLedgerCommitNode(name="Guard"),
        actor_id=actor_id,
    )

    assert result.status == expected
