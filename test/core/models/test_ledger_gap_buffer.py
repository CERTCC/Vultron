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
"""Unit tests for :class:`LedgerGapBuffer` (issue #1556, SYNC-10-004)."""

import pytest

from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.ledger_gap_buffer import (
    LedgerGapBuffer,
    _reset_buffers,
    get_ledger_gap_buffer,
)

CASE_A = "https://example.org/cases/a"
CASE_B = "https://example.org/cases/b"


@pytest.fixture(autouse=True)
def _clear_registry():
    _reset_buffers()
    yield
    _reset_buffers()


def _entry(
    log_index: int, prev_hash: str, case_id: str = CASE_A
) -> VultronCaseLedgerEntry:
    chain = HashChainLedgerRecord(
        case_id=case_id,
        log_index=log_index,
        object_id=f"{case_id}/activities/act-{log_index}",
        event_type="test_event",
        payload_snapshot={"log_index": log_index},
        prev_log_hash=prev_hash,
    )
    return VultronCaseLedgerEntry(
        case_id=chain.case_id,
        log_index=chain.log_index,
        disposition=chain.disposition,
        term=chain.term,
        log_object_id=chain.object_id,
        event_type=chain.event_type,
        payload_snapshot=dict(chain.payload_snapshot),
        prev_log_hash=chain.prev_log_hash,
        entry_hash=chain.entry_hash,
    )


def _chain(length: int, case_id: str = CASE_A) -> list[VultronCaseLedgerEntry]:
    entries: list[VultronCaseLedgerEntry] = []
    prev = "0" * 64
    for i in range(length):
        entry = _entry(i, prev, case_id)
        entries.append(entry)
        prev = entry.entry_hash
    return entries


class TestBufferAndTakeNext:
    def test_take_next_returns_none_when_empty(self):
        buf = LedgerGapBuffer()
        assert buf.take_next(CASE_A, "0" * 64) is None

    def test_buffer_then_take_next_by_predecessor_hash(self):
        buf = LedgerGapBuffer()
        e0, e1 = _chain(2)
        assert buf.buffer(e1) is True
        assert buf.depth(CASE_A) == 1
        # e1's predecessor is e0; keyed on e1.prev_log_hash == e0.entry_hash.
        taken = buf.take_next(CASE_A, e0.entry_hash)
        assert taken is not None
        assert taken.log_index == 1
        assert buf.depth(CASE_A) == 0

    def test_take_next_wrong_tail_returns_none(self):
        buf = LedgerGapBuffer()
        _e0, e1, _e2 = _chain(3)
        buf.buffer(e1)
        # A tail hash that nothing extends yields None (entry stays buffered).
        assert buf.take_next(CASE_A, "deadbeef" * 8) is None
        assert buf.depth(CASE_A) == 1

    def test_cascade_drain_in_order(self):
        """A contiguous buffered run drains one hop at a time in O(1) lookups."""
        entries = _chain(5)  # 0..4
        buf = LedgerGapBuffer()
        for e in entries[1:]:  # buffer 1,2,3,4
            buf.buffer(e)
        assert buf.depth(CASE_A) == 4

        tail = entries[0].entry_hash  # pretend 0 was just persisted
        drained = []
        while (nxt := buf.take_next(CASE_A, tail)) is not None:
            drained.append(nxt.log_index)
            tail = nxt.entry_hash
        assert drained == [1, 2, 3, 4]
        assert buf.depth(CASE_A) == 0

    def test_cases_are_isolated(self):
        buf = LedgerGapBuffer()
        a0, a1 = _chain(2, CASE_A)
        b0, b1 = _chain(2, CASE_B)
        buf.buffer(a1)
        buf.buffer(b1)
        assert buf.depth(CASE_A) == 1
        assert buf.depth(CASE_B) == 1
        # Draining case A's tail must not touch case B.
        assert buf.take_next(CASE_A, a0.entry_hash) is not None
        assert buf.depth(CASE_B) == 1
        assert buf.take_next(CASE_B, b0.entry_hash) is not None


class TestDuplicatesAndForks:
    def test_exact_duplicate_is_noop(self):
        buf = LedgerGapBuffer()
        _e0, e1 = _chain(2)
        assert buf.buffer(e1) is True
        assert buf.buffer(e1) is True
        assert buf.depth(CASE_A) == 1

    def test_fork_replaces_and_warns(self, caplog):
        buf = LedgerGapBuffer()
        _e0, e1 = _chain(2)
        # A second entry sharing e1's prev_log_hash but a different content
        # hash is a fork; the newer one replaces it (WARNING logged).
        fork = _entry(1, e1.prev_log_hash)
        object.__setattr__(fork, "entry_hash", "f" * 64)
        buf.buffer(e1)
        with caplog.at_level("WARNING"):
            buf.buffer(fork)
        assert buf.depth(CASE_A) == 1
        assert any("forked" in r.message for r in caplog.records)


class TestSizeBound:
    def test_zero_max_disables_buffering(self):
        buf = LedgerGapBuffer(max_entries=0)
        _e0, e1 = _chain(2)
        assert buf.buffer(e1) is False
        assert buf.depth(CASE_A) == 0

    def test_full_buffer_evicts_farthest_ahead(self, caplog):
        """When full, the farthest-ahead entry is evicted to admit a closer one."""
        entries = _chain(6)  # 0..5
        buf = LedgerGapBuffer(max_entries=2)
        # Buffer the two farthest-ahead entries (4, 5).
        buf.buffer(entries[4])
        buf.buffer(entries[5])
        assert buf.depth(CASE_A) == 2
        # A closer entry (2) should evict the farthest (5) and be admitted.
        with caplog.at_level("WARNING"):
            assert buf.buffer(entries[2]) is True
        assert buf.depth(CASE_A) == 2
        # Index 5 (farthest) is gone; index 2 present.
        assert buf.take_next(CASE_A, entries[1].entry_hash) is not None
        assert buf.take_next(CASE_A, entries[4].entry_hash) is None

    def test_full_buffer_drops_incoming_when_it_is_farthest(self, caplog):
        entries = _chain(6)
        buf = LedgerGapBuffer(max_entries=2)
        buf.buffer(entries[2])
        buf.buffer(entries[3])
        with caplog.at_level("WARNING"):
            # index 5 is farther ahead than everything buffered → dropped.
            assert buf.buffer(entries[5]) is False
        assert buf.depth(CASE_A) == 2


class TestRegistry:
    def test_get_ledger_gap_buffer_is_per_actor_singleton(self):
        a = get_ledger_gap_buffer("actor-1")
        b = get_ledger_gap_buffer("actor-1")
        c = get_ledger_gap_buffer("actor-2")
        assert a is b
        assert a is not c

    def test_reset_buffers_clears_registry(self):
        a = get_ledger_gap_buffer("actor-1")
        _reset_buffers()
        assert get_ledger_gap_buffer("actor-1") is not a
