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
"""Unit tests for :func:`vultron.core.sync_helpers.is_ledger_fresh_for_case`
and :func:`vultron.core.sync_helpers._reconstruct_tail_hash`.

Spec: SYNC-10-003, SYNC-10-004, SYNC-10-005, CLP-08-004, CLP-08-005.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import (
    HashChainLedgerRecord,
)
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.sync_helpers import (
    _find_equivalent_recorded_entry,
    _reconstruct_tail_hash,
    is_ledger_fresh_for_case,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.errors import VultronValidationError

CASE_ID = "https://example.org/cases/catchup-test"
CASE_ACTOR_ID = "https://example.org/actors/case-actor"
OTHER_CASE_ID = "https://example.org/cases/other"
_ZERO_HASH: str = "0" * 64  # arbitrary hash for non-genesis test chains


@pytest.fixture
def dl():
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )


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


class TestReconstructTailHash:
    def test_empty_log_with_case_returns_genesis(self, dl):
        """CLP-08-005: empty ledger returns per-case genesis hash."""
        case = _make_case()
        dl.save(case)
        tail_hash, tail_index = _reconstruct_tail_hash(CASE_ID, dl)
        assert tail_hash == case.genesis_hash
        assert len(tail_hash) == 64
        assert tail_index == -1

    def test_empty_log_no_case_raises(self, dl):
        """CLP-08-005 fail-closed: no case in DataLayer raises VultronValidationError."""
        with pytest.raises(VultronValidationError, match="genesis hash"):
            _reconstruct_tail_hash(CASE_ID, dl)


class TestContiguousChain:
    def test_single_genesis_entry_is_fresh(self, dl):
        case = _make_case()
        dl.save(case)
        _store(dl, _entry(0, case.genesis_hash))
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is True, reason

    def test_two_entry_chain_is_fresh(self, dl):
        case = _make_case()
        dl.save(case)
        e0 = _store(dl, _entry(0, case.genesis_hash))
        _store(dl, _entry(1, e0.entry_hash))
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is True, reason

    def test_three_entry_chain_is_fresh(self, dl):
        case = _make_case()
        dl.save(case)
        e0 = _store(dl, _entry(0, case.genesis_hash))
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
        case = _make_case()
        dl.save(case)
        e0 = _store(dl, _entry(0, case.genesis_hash))
        # Skip index 1; add entry at index 2 referencing e0's hash
        _store(dl, _entry(2, e0.entry_hash))
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is False
        assert "gap" in reason or "jump" in reason

    def test_no_case_in_dl_with_entries_is_stale(self, dl):
        """Fail-closed: entries present but case not in DataLayer → stale.

        CLP-08-004: genesis hash is unavailable when the case record is
        absent, so origin binding cannot be verified.
        """
        _store(dl, _entry(0, _ZERO_HASH))
        fresh, reason = is_ledger_fresh_for_case(CASE_ID, dl)
        assert fresh is False
        assert "genesis hash unavailable" in reason

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
        case = _make_case()
        dl.save(case)
        _store(dl, _entry(0, case.genesis_hash))
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
        case = _make_case()
        dl.save(case)
        e0 = _store(dl, _entry(0, case.genesis_hash))
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


class TestEquivalentRecordedEntry:
    """``_find_equivalent_recorded_entry`` is what makes a retry idempotent.

    A miss appends a *new* ledger index for an assertion already recorded, which
    is exactly the ledger-index instability ADR-0041 forbids.  The snapshots a
    retry rebuilds are not byte-identical to the originals: ``as_Base`` stamps
    ``published`` and ``updated`` with ``now_utc`` at construction, so every
    embedded object gets a fresh pair whenever the snapshot is rebuilt.  These
    tests fix which differences count.
    """

    _OBJECT_ID = "https://example.org/activities/log-0"
    _EVENT = "add_participant_status_to_participant"

    def _snapshot(self, stamp: str, rm_state: str = "RECEIVED") -> dict:
        """A snapshot in the shape ``build_add_participant_status_snapshot``
        produces: a re-rendered object *and* a re-rendered target whose own
        nested status list carries timestamps too."""
        return {
            "type": "Add",
            "actor": CASE_ACTOR_ID,
            "context": CASE_ID,
            "object": {
                "id": "https://example.org/statuses/ps-0",
                "type": "ParticipantStatus",
                "rmState": rm_state,
                "published": stamp,
                "updated": stamp,
            },
            "target": {
                "id": "https://example.org/participants/p-0",
                "type": "CaseParticipant",
                "published": stamp,
                "updated": stamp,
                "participantStatuses": [
                    {
                        "id": "https://example.org/statuses/ps-0",
                        "rmState": rm_state,
                        "published": stamp,
                        "updated": stamp,
                    }
                ],
            },
        }

    def _record(self, dl, snapshot: dict) -> VultronCaseLedgerEntry:
        entry = VultronCaseLedgerEntry(
            case_id=CASE_ID,
            log_index=0,
            log_object_id=self._OBJECT_ID,
            event_type=self._EVENT,
            payload_snapshot=snapshot,
            prev_log_hash=_ZERO_HASH,
            entry_hash="a" * 64,
        )
        dl.save(entry)
        return entry

    def _find(self, dl, snapshot: dict):
        return _find_equivalent_recorded_entry(
            case_id=CASE_ID,
            object_id=self._OBJECT_ID,
            event_type=self._EVENT,
            payload_snapshot=snapshot,
            dl=dl,
        )

    def test_a_rebuilt_snapshot_still_matches(self, dl):
        """The regression: only the restamped timestamps differ, at every depth.

        ``now_utc`` truncates to whole seconds, so byte equality made this a
        coin flip on whether the retry landed in the same second as the
        original — passing locally and failing on slower CI.
        """
        self._record(dl, self._snapshot("2026-01-01T00:00:00+00:00"))

        found = self._find(dl, self._snapshot("2026-01-01T00:00:07+00:00"))

        assert found is not None, (
            "a retry whose snapshot differs only in restamped published/updated"
            " values is the same assertion, and must not append a new index"
        )
        assert found.log_index == 0

    def test_a_real_difference_still_misses(self, dl):
        """The dedup must stay a dedup: a changed state is a new assertion.

        Timestamps are dropped from the comparison, not the whole payload — if
        they were, a genuine status change carrying the same object id would be
        swallowed and never recorded.
        """
        self._record(dl, self._snapshot("2026-01-01T00:00:00+00:00"))

        found = self._find(
            dl, self._snapshot("2026-01-01T00:00:00+00:00", rm_state="VALID")
        )

        assert found is None

    def test_a_rejected_entry_is_not_a_match(self, dl):
        """Only ``recorded`` entries count; a rejection is not an assertion."""
        snapshot = self._snapshot("2026-01-01T00:00:00+00:00")
        entry = self._record(dl, snapshot)
        entry.disposition = "rejected"
        entry.reason_code = "invalid"
        dl.save(entry)

        assert (
            self._find(dl, self._snapshot("2026-01-01T00:00:09+00:00")) is None
        )
