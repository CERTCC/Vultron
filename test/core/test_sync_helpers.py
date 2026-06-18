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
"""Unit tests for :func:`vultron.core.sync_helpers.is_ledger_fresh_for_case`.

Spec: SYNC-10-003, SYNC-10-004, SYNC-10-005.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import (
    HashChainLedgerRecord,
)
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.sync_helpers import is_ledger_fresh_for_case
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry

CASE_ID = "https://example.org/cases/catchup-test"
CASE_ACTOR_ID = "https://example.org/actors/case-actor"
OTHER_CASE_ID = "https://example.org/cases/other"
_ZERO_HASH: str = "0" * 64  # arbitrary hash for non-genesis test chains


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


def _make_case(
    case_id: str = CASE_ID, case_actor_id: str = CASE_ACTOR_ID
) -> VulnerabilityCase:
    """Create a VulnerabilityCase with computed genesis_hash."""
    return VulnerabilityCase(id_=case_id, attributed_to=case_actor_id)


def _entry(
    log_index: int, prev_hash: str, case_id: str = CASE_ID
) -> VultronCaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=case_id,
            log_index=log_index,
            object_id=f"https://example.org/activities/log-{log_index}",
            event_type="test_event",
            payload_snapshot={"log_index": log_index},
            prev_log_hash=prev_hash,
        )
    )


def _store(
    dl: SqliteDataLayer, entry: VultronCaseLedgerEntry
) -> VultronCaseLedgerEntry:
    dl.save(entry)
    return entry


class TestEmptyLedger:
    def test_empty_ledger_is_fresh(self, dl):
        """SYNC-10-005: empty prefix is trivially contiguous."""
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is True
        assert reason == ""


class TestContiguousChain:
    def test_single_genesis_entry_is_fresh(self, dl):
        _store(dl, _entry(0, _ZERO_HASH))
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is True, reason

    def test_two_entry_chain_is_fresh(self, dl):
        e0 = _store(dl, _entry(0, _ZERO_HASH))
        _store(dl, _entry(1, e0.entry_hash))
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is True, reason

    def test_three_entry_chain_is_fresh(self, dl):
        e0 = _store(dl, _entry(0, _ZERO_HASH))
        e1 = _store(dl, _entry(1, e0.entry_hash))
        _store(dl, _entry(2, e1.entry_hash))
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is True, reason

    def test_per_case_genesis_hash_chain_is_fresh(self, dl):
        """CLP-08-004: chain anchored to per-case genesis hash is accepted as fresh.

        Positive path: with a VulnerabilityCase in the DataLayer, the genesis
        hash check is active; a correctly-anchored chain must still return fresh.
        """
        case = _make_case()
        dl.save(case)
        e0 = _store(dl, _entry(0, case.genesis_hash))
        e1 = _store(dl, _entry(1, e0.entry_hash))
        _store(dl, _entry(2, e1.entry_hash))
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is True, reason

    def test_only_checks_entries_for_requested_case(self, dl):
        """Other cases' entries do not affect freshness of the requested case."""
        # Store entries for another case
        other_e0 = _store(dl, _entry(0, _ZERO_HASH, case_id=OTHER_CASE_ID))
        _store(dl, _entry(1, other_e0.entry_hash, case_id=OTHER_CASE_ID))
        # Requested case is empty → fresh
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is True, reason


class TestMissingGenesisEntry:
    def test_missing_genesis_is_stale(self, dl):
        """SYNC-10-004: first entry must be at log_index=0."""
        e1 = _store(dl, _entry(0, _ZERO_HASH))
        # Manually create an entry at index 2 with no index-1 entry
        _store(dl, _entry(2, e1.entry_hash))
        # e1 (index 0) exists but jumps to index 2 → gap
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is False
        assert "gap" in reason or "jump" in reason

    def test_non_zero_first_index_is_stale(self, dl):
        """Actor has no genesis entry; its first stored entry has index > 0."""
        # Create a single entry at index 1 (skipping genesis)
        e = VultronCaseLedgerEntry(
            case_id=CASE_ID,
            log_index=1,
            log_object_id="https://example.org/activities/orphan",
            event_type="test_event",
            payload_snapshot={"note": "no genesis"},
            prev_log_hash=_ZERO_HASH,
            entry_hash="0" * 64,
        )
        dl.save(e)
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is False
        assert "genesis entry missing" in reason or "log_index=1" in reason


class TestHashMismatch:
    def test_wrong_prev_log_hash_is_stale(self, dl):
        """SYNC-10-004: hash mismatch at any link is stale."""
        _store(dl, _entry(0, _ZERO_HASH))
        # Build e1 with a deliberately wrong prev_log_hash
        bad_prev = "a" * 64
        bad_e1 = VultronCaseLedgerEntry(
            case_id=CASE_ID,
            log_index=1,
            log_object_id="https://example.org/activities/log-1",
            event_type="test_event",
            payload_snapshot={"log_index": 1},
            prev_log_hash=bad_prev,
            entry_hash="b" * 64,
        )
        dl.save(bad_e1)
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is False
        assert "hash mismatch" in reason

    def test_wrong_genesis_prev_hash_is_stale(self, dl):
        """Genesis entry prev_log_hash must match the per-case genesis hash."""
        case = _make_case()
        dl.save(case)
        bad_genesis = VultronCaseLedgerEntry(
            case_id=CASE_ID,
            log_index=0,
            log_object_id="https://example.org/activities/log-0",
            event_type="test_event",
            payload_snapshot={"log_index": 0},
            prev_log_hash="c" * 64,  # not the per-case genesis hash
            entry_hash="d" * 64,
        )
        dl.save(bad_genesis)
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is False
        assert "prev_log_hash mismatch" in reason or "genesis" in reason


class TestIndexGap:
    def test_gap_in_middle_is_stale(self, dl):
        """Entries 0, 1, 3 (missing 2) is a gap → stale."""
        e0 = _store(dl, _entry(0, _ZERO_HASH))
        e1 = _store(dl, _entry(1, e0.entry_hash))
        # Skip index 2; build entry at index 3 referencing e1's hash
        e3 = VultronCaseLedgerEntry(
            case_id=CASE_ID,
            log_index=3,
            log_object_id="https://example.org/activities/log-3",
            event_type="test_event",
            payload_snapshot={"log_index": 3},
            prev_log_hash=e1.entry_hash,
            entry_hash="e" * 64,
        )
        dl.save(e3)
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is False
        assert "gap" in reason or "jump" in reason
