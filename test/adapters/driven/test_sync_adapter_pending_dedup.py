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

"""``SyncActivityAdapter.send_announce_log_entry`` does not queue a row it holds.

SYNC-15-012: an ``Announce(CaseLedgerEntry)`` for an (entry, peer) pair that is
still pending in this actor's outbox is not queued a second time, and the
caller is told so.  A row already popped for delivery is no longer pending, so
a later request for the same pair queues again — the guard is against
duplicates *in the queue*, not against ever re-sending.
"""

import json

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import (
    SyncActivityAdapter,
    _read_queued_row,
)
from vultron.adapters.outbox_sealed_body import (
    SealedOutboundBody,
    sealed_body_id,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry

OWNER = "https://example.org/actors/owner"
PEER_A = "https://example.org/actors/a"
PEER_B = "https://example.org/actors/b"
CASE = "https://example.org/cases/c"


def _entry(index: int) -> CaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE,
            log_index=index,
            object_id=f"urn:test:activity-{index}",
            semantic_type="add_note",
            payload_snapshot={"log_index": index},
            prev_log_hash="0" * 64,
        )
    )


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=OWNER)


@pytest.mark.spec("SYNC-15-012")
def test_same_entry_same_peer_is_queued_once_while_pending(dl):
    adapter = SyncActivityAdapter(dl)
    entry = _entry(1)

    assert adapter.send_announce_log_entry(entry, OWNER, [PEER_A]) is True
    assert adapter.send_announce_log_entry(entry, OWNER, [PEER_A]) is False

    assert len(dl.outbox_list()) == 1


@pytest.mark.spec("SYNC-15-012")
def test_same_entry_to_another_peer_is_still_queued(dl):
    adapter = SyncActivityAdapter(dl)
    entry = _entry(1)

    assert adapter.send_announce_log_entry(entry, OWNER, [PEER_A]) is True
    assert adapter.send_announce_log_entry(entry, OWNER, [PEER_B]) is True

    assert len(dl.outbox_list()) == 2


@pytest.mark.spec("SYNC-15-012")
def test_once_popped_for_delivery_the_pair_can_be_queued_again(dl):
    adapter = SyncActivityAdapter(dl)
    entry = _entry(1)
    adapter.send_announce_log_entry(entry, OWNER, [PEER_A])
    assert dl.outbox_pop() is not None  # the drain took it

    assert adapter.send_announce_log_entry(entry, OWNER, [PEER_A]) is True
    assert len(dl.outbox_list()) == 1


@pytest.mark.spec("ID-04-004")
def test_same_mismatching_entry_is_rejected_under_one_id(dl):
    adapter = SyncActivityAdapter(dl)
    entry = _entry(2)

    adapter.send_reject_log_entry(entry, "a" * 64, OWNER, [PEER_A])
    (first,) = dl.outbox_list()
    assert dl.outbox_pop() == first  # the drain took it
    adapter.send_reject_log_entry(entry, "a" * 64, OWNER, [PEER_A])
    adapter.send_reject_log_entry(entry, "a" * 64, OWNER, [PEER_A])

    # Queued again under the same id (the receiver deduplicates), once.
    assert dl.outbox_list() == [first]


@pytest.mark.spec("ID-04-005")
def test_a_sealed_reject_that_was_never_queued_is_queued_on_redelivery(dl):
    from vultron.adapters.outbox_sealed_body import is_sealed
    from vultron.core.models.activity_ids import derived_activity_id

    adapter = SyncActivityAdapter(dl)
    entry = _entry(2)
    adapter.send_reject_log_entry(entry, "a" * 64, OWNER, [PEER_A])
    (reject_id,) = dl.outbox_list()
    assert reject_id == derived_activity_id(
        "reject-log-entry", OWNER, entry.id_, "a" * 64, PEER_A
    )
    # A crash between sealing and queueing: sealed, nothing queued.
    dl.outbox_pop()
    assert is_sealed(dl, reject_id) and dl.outbox_list() == []

    adapter.send_reject_log_entry(entry, "a" * 64, OWNER, [PEER_A])

    assert dl.outbox_list() == [reject_id]


@pytest.mark.spec("ID-04-004")
def test_a_different_tail_hash_is_a_new_rejection(dl):
    adapter = SyncActivityAdapter(dl)
    entry = _entry(2)

    adapter.send_reject_log_entry(entry, "a" * 64, OWNER, [PEER_A])
    adapter.send_reject_log_entry(entry, "b" * 64, OWNER, [PEER_A])

    assert len(dl.outbox_list()) == 2


def _queue_announce(dl: SqliteDataLayer, entry: CaseLedgerEntry, to: str):
    """Queue an ``Announce`` of *entry* to *to*, as a fresh adapter would."""
    assert SyncActivityAdapter(dl).send_announce_log_entry(entry, OWNER, [to])


@pytest.mark.spec("SYNC-15-012")
def test_the_pending_index_reads_sealed_bodies_not_activity_records(
    dl, monkeypatch
):
    """A fresh adapter indexes the queue without rehydrating its activities.

    The index is rebuilt by every adapter, and one is composed per received
    activity, so a hydrating read of every queued ``Announce`` made each
    fan-out cost O(queue) model validations (#4906).  The sealed body is what
    the outbox delivers (VM-08-003), so it is what the index reads.
    """
    for index in range(3):
        _queue_announce(dl, _entry(index), PEER_A)
    queued = set(dl.outbox_list())
    read_ids: list[str] = []
    original_read = dl.read

    def _spy(object_id: str, *args, **kwargs):
        read_ids.append(object_id)
        return original_read(object_id, *args, **kwargs)

    monkeypatch.setattr(dl, "read", _spy)

    adapter = SyncActivityAdapter(dl)
    assert adapter.send_announce_log_entry(_entry(1), OWNER, [PEER_A]) is False

    assert queued.isdisjoint(read_ids), sorted(queued & set(read_ids))


@pytest.mark.spec("SYNC-15-012")
def test_a_fresh_adapter_sees_the_rows_another_adapter_queued(dl):
    """The index is the store's queue, not the adapter's own history."""
    _queue_announce(dl, _entry(1), PEER_A)

    adapter = SyncActivityAdapter(dl)

    assert adapter.send_announce_log_entry(_entry(1), OWNER, [PEER_A]) is False
    assert adapter.send_announce_log_entry(_entry(1), OWNER, [PEER_B]) is True
    assert len(dl.outbox_list()) == 2


@pytest.mark.spec("SYNC-15-012")
def test_a_queued_row_with_no_sealed_body_is_not_pending(dl):
    """A row the outbox cannot deliver does not stand in for a real one.

    The outbox delivers only the sealed body (OX-07-001); a queued id with
    none is never delivered, so it must not suppress the Announce that would
    be (SYNC-15-012).
    """
    dl.outbox_append("urn:test:unsealed-announce")

    adapter = SyncActivityAdapter(dl)

    assert adapter.send_announce_log_entry(_entry(1), OWNER, [PEER_A]) is True


@pytest.mark.spec("SYNC-15-012")
def test_each_send_reads_only_the_rows_queued_since_the_last(dl, monkeypatch):
    """A fan-out does not re-read the whole queue for every Announce.

    Every send queues a row, so the queue changes between any two sends; a
    rebuild that re-read every row made *n* sends cost O(n × queue) reads
    (#4906).  A sealed body is write-once, so a row read once stays read.
    """
    adapter = SyncActivityAdapter(dl)
    for index in range(4):
        assert adapter.send_announce_log_entry(_entry(index), OWNER, [PEER_A])
    read_ids: list[str] = []
    original_read = dl.read

    def _spy(object_id: str, *args, **kwargs):
        read_ids.append(object_id)
        return original_read(object_id, *args, **kwargs)

    monkeypatch.setattr(dl, "read", _spy)
    newest = dl.outbox_list()[-1]

    assert adapter.send_announce_log_entry(_entry(9), OWNER, [PEER_A])

    queued_reads = [
        object_id
        for object_id in read_ids
        if any(object_id.startswith(a) for a in dl.outbox_list()[:-1])
    ]
    assert all(object_id.startswith(newest) for object_id in queued_reads), (
        queued_reads
    )
    assert len(queued_reads) == 1, queued_reads


def _seal_raw(dl: SqliteDataLayer, activity_id: str, body: dict) -> None:
    """Seal *body* under *activity_id* as written, bypassing any factory."""
    dl.save(
        SealedOutboundBody(
            id_=sealed_body_id(activity_id),
            activity_id=activity_id,
            body=json.dumps(body),
        )
    )


_ENTRY = {"type": "CaseLedgerEntry", "id": "urn:test:entry"}


@pytest.mark.spec("SYNC-15-012")
@pytest.mark.parametrize(
    ("body", "entry_id", "recipients"),
    [
        (
            {"type": "Announce", "object": _ENTRY, "to": [PEER_A, PEER_B]},
            "urn:test:entry",
            {PEER_A, PEER_B},
        ),
        (
            {"type": "Announce", "object": _ENTRY, "to": PEER_A},
            "urn:test:entry",
            {PEER_A},
        ),
        (
            {"type": "Announce", "object": _ENTRY, "to": [{"id": PEER_A}]},
            "urn:test:entry",
            {PEER_A},
        ),
        ({"type": "Reject", "object": _ENTRY, "to": [PEER_A]}, None, set()),
        ({"type": "Announce", "object": "urn:test:entry"}, None, set()),
        (
            {"type": "Announce", "object": {"type": "Note", "id": "urn:n"}},
            None,
            set(),
        ),
        (
            {"type": "Announce", "object": {"type": "CaseLedgerEntry"}},
            None,
            set(),
        ),
    ],
    ids=[
        "announce",
        "bare-recipient",
        "recipient-object",
        "not-an-announce",
        "entry-by-reference",
        "not-a-ledger-entry",
        "entry-without-id",
    ],
)
def test_a_queued_row_is_read_from_its_sealed_body(
    dl, body, entry_id, recipients
):
    """Only an ``Announce`` carrying an identified entry is indexed."""
    _seal_raw(dl, "urn:test:row", body)

    row = _read_queued_row(dl, "urn:test:row")

    assert row is not None
    assert row.entry_id == entry_id
    assert row.recipients == recipients


@pytest.mark.spec("SYNC-15-012")
def test_a_row_sealed_after_it_was_read_is_indexed_then(dl):
    """An unsealed row is not remembered as unsealed by the adapter."""
    entry = _entry(1)
    dl.outbox_append("urn:test:late-seal")
    adapter = SyncActivityAdapter(dl)
    assert adapter.send_announce_log_entry(_entry(2), OWNER, [PEER_A])

    _seal_raw(
        dl,
        "urn:test:late-seal",
        {
            "type": "Announce",
            "object": {"type": "CaseLedgerEntry", "id": entry.id_},
            "to": [PEER_B],
        },
    )

    assert adapter.send_announce_log_entry(entry, OWNER, [PEER_B]) is False
