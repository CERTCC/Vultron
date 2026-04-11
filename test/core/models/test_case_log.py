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

"""Unit tests for CaseLogEntry, CaseEventLog, ReplicationState, and BTBridge
leadership guard.

Covers:

- ``CaseLogEntry`` construction, auto-hash computation, and ``verify_hash``
  (SYNC-07-001, CLP-02-001 through CLP-02-007).
- ``CaseEventLog`` append-only semantics, hash-chain integrity,
  ``tail_hash``, ``recorded_entries`` projection, and ``verify_chain``
  (SYNC-01-001, SYNC-01-002, SYNC-01-003, SYNC-07-001,
  CLP-04-001, CLP-04-003).
- ``ReplicationState`` construction and DataLayer serialisation
  (SYNC-04-001, SYNC-04-002).
- ``BTBridge`` leadership guard port — default always-True behaviour and
  non-leader short-circuit (SYNC-09-003).
"""

import hashlib
import json
from unittest.mock import MagicMock

import py_trees
import pytest

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.models.case_log import (
    GENESIS_HASH,
    CaseEventLog,
    CaseLogEntry,
    ReplicationState,
    _canonical_bytes,
    _sha256_hex,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "urn:uuid:case-1234"
OBJECT_ID = "urn:uuid:report-5678"


@pytest.fixture()
def empty_log() -> CaseEventLog:
    return CaseEventLog(case_id=CASE_ID)


@pytest.fixture()
def log_with_one_entry(empty_log: CaseEventLog) -> CaseEventLog:
    empty_log.append(object_id=OBJECT_ID, event_type="report_received")
    return empty_log


@pytest.fixture()
def log_with_three_entries(empty_log: CaseEventLog) -> CaseEventLog:
    empty_log.append(
        object_id="urn:uuid:obj1",
        event_type="report_received",
        payload_snapshot={"id": "urn:uuid:obj1"},
    )
    empty_log.append(
        object_id="urn:uuid:obj2",
        event_type="case_created",
        payload_snapshot={"id": "urn:uuid:obj2"},
    )
    empty_log.append(
        object_id="urn:uuid:obj3",
        event_type="participant_added",
        disposition="recorded",
    )
    return empty_log


# ---------------------------------------------------------------------------
# _canonical_bytes / _sha256_hex helpers
# ---------------------------------------------------------------------------


class TestCanonicalHelpers:
    def test_canonical_bytes_sorted_keys(self):
        data = {"z": 1, "a": 2, "m": 3}
        result = _canonical_bytes(data)
        parsed = json.loads(result.decode("utf-8"))
        assert list(parsed.keys()) == ["a", "m", "z"]

    def test_canonical_bytes_compact_no_whitespace(self):
        result = _canonical_bytes({"key": "value"})
        assert b" " not in result

    def test_sha256_hex_returns_64_char_hex(self):
        digest = _sha256_hex({"foo": "bar"})
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_sha256_hex_deterministic(self):
        data = {"a": 1, "b": 2}
        assert _sha256_hex(data) == _sha256_hex(data)

    def test_sha256_hex_matches_manual(self):
        data = {"key": "value"}
        canonical = json.dumps(
            data, sort_keys=True, separators=(",", ":"), default=str
        )
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert _sha256_hex(data) == expected


# ---------------------------------------------------------------------------
# GENESIS_HASH
# ---------------------------------------------------------------------------


class TestGenesisHash:
    def test_genesis_hash_is_64_zeros(self):
        assert GENESIS_HASH == "0" * 64

    def test_genesis_hash_length(self):
        assert len(GENESIS_HASH) == 64


# ---------------------------------------------------------------------------
# CaseLogEntry
# ---------------------------------------------------------------------------


class TestCaseLogEntry:
    def test_construction_sets_required_fields(self):
        entry = CaseLogEntry(
            case_id=CASE_ID,
            log_index=0,
            object_id=OBJECT_ID,
            event_type="report_received",
            prev_log_hash=GENESIS_HASH,
        )
        assert entry.case_id == CASE_ID
        assert entry.log_index == 0
        assert entry.object_id == OBJECT_ID
        assert entry.event_type == "report_received"
        assert entry.prev_log_hash == GENESIS_HASH

    def test_entry_hash_auto_computed(self):
        entry = CaseLogEntry(
            case_id=CASE_ID,
            log_index=0,
            object_id=OBJECT_ID,
            event_type="report_received",
            prev_log_hash=GENESIS_HASH,
        )
        assert entry.entry_hash != ""
        assert len(entry.entry_hash) == 64

    def test_entry_hash_verify_hash_passes(self):
        entry = CaseLogEntry(
            case_id=CASE_ID,
            log_index=0,
            object_id=OBJECT_ID,
            event_type="report_received",
            prev_log_hash=GENESIS_HASH,
        )
        assert entry.verify_hash()

    def test_entry_hash_tamper_detection(self):
        entry = CaseLogEntry(
            case_id=CASE_ID,
            log_index=0,
            object_id=OBJECT_ID,
            event_type="report_received",
            prev_log_hash=GENESIS_HASH,
        )
        # Manually tamper with object_id after creation
        object.__setattr__(entry, "object_id", "urn:uuid:tampered")
        assert not entry.verify_hash()

    def test_default_disposition_is_recorded(self):
        entry = CaseLogEntry(
            case_id=CASE_ID,
            log_index=0,
            object_id=OBJECT_ID,
            event_type="test",
            prev_log_hash=GENESIS_HASH,
        )
        assert entry.disposition == "recorded"

    def test_rejected_disposition(self):
        entry = CaseLogEntry(
            case_id=CASE_ID,
            log_index=0,
            object_id=OBJECT_ID,
            event_type="test",
            prev_log_hash=GENESIS_HASH,
            disposition="rejected",
            reason_code="INVALID_STATE",
        )
        assert entry.disposition == "rejected"
        assert entry.reason_code == "INVALID_STATE"

    def test_term_defaults_to_none(self):
        entry = CaseLogEntry(
            case_id=CASE_ID,
            log_index=0,
            object_id=OBJECT_ID,
            event_type="test",
            prev_log_hash=GENESIS_HASH,
        )
        assert entry.term is None

    def test_different_entries_have_different_hashes(self):
        e1 = CaseLogEntry(
            case_id=CASE_ID,
            log_index=0,
            object_id="urn:uuid:obj1",
            event_type="test",
            prev_log_hash=GENESIS_HASH,
        )
        e2 = CaseLogEntry(
            case_id=CASE_ID,
            log_index=0,
            object_id="urn:uuid:obj2",
            event_type="test",
            prev_log_hash=GENESIS_HASH,
        )
        assert e1.entry_hash != e2.entry_hash

    def test_entry_hash_not_in_hashable_dict(self):
        """entry_hash MUST be excluded from the content that is hashed."""
        entry = CaseLogEntry(
            case_id=CASE_ID,
            log_index=0,
            object_id=OBJECT_ID,
            event_type="test",
            prev_log_hash=GENESIS_HASH,
        )
        hashable = entry._hashable_dict()
        assert "entry_hash" not in hashable

    def test_payload_snapshot_stored_as_dict(self):
        snap = {"id": OBJECT_ID, "type": "Offer"}
        entry = CaseLogEntry(
            case_id=CASE_ID,
            log_index=0,
            object_id=OBJECT_ID,
            event_type="test",
            prev_log_hash=GENESIS_HASH,
            payload_snapshot=snap,
        )
        assert entry.payload_snapshot == snap

    def test_reason_detail_optional(self):
        entry = CaseLogEntry(
            case_id=CASE_ID,
            log_index=0,
            object_id=OBJECT_ID,
            event_type="test",
            prev_log_hash=GENESIS_HASH,
            disposition="rejected",
            reason_code="PRECONDITION_FAILED",
            reason_detail="Case is already closed",
        )
        assert entry.reason_detail == "Case is already closed"


# ---------------------------------------------------------------------------
# CaseEventLog — append semantics
# ---------------------------------------------------------------------------


class TestCaseEventLogAppend:
    def test_empty_log_tail_hash_is_genesis(self, empty_log: CaseEventLog):
        assert empty_log.tail_hash == GENESIS_HASH

    def test_empty_log_next_index_is_zero(self, empty_log: CaseEventLog):
        assert empty_log.next_index == 0

    def test_first_entry_log_index_is_zero(
        self, log_with_one_entry: CaseEventLog
    ):
        assert log_with_one_entry.entries[0].log_index == 0

    def test_first_entry_prev_hash_is_genesis(
        self, log_with_one_entry: CaseEventLog
    ):
        assert log_with_one_entry.entries[0].prev_log_hash == GENESIS_HASH

    def test_tail_hash_updates_after_append(
        self, log_with_one_entry: CaseEventLog
    ):
        assert (
            log_with_one_entry.tail_hash
            == log_with_one_entry.entries[0].entry_hash
        )

    def test_second_entry_prev_hash_equals_first_entry_hash(
        self, empty_log: CaseEventLog
    ):
        e1 = empty_log.append(object_id="urn:uuid:a", event_type="first")
        e2 = empty_log.append(object_id="urn:uuid:b", event_type="second")
        assert e2.prev_log_hash == e1.entry_hash

    def test_log_indices_monotonically_increase(
        self, log_with_three_entries: CaseEventLog
    ):
        for i, entry in enumerate(log_with_three_entries.entries):
            assert entry.log_index == i

    def test_next_index_increments(self, empty_log: CaseEventLog):
        assert empty_log.next_index == 0
        empty_log.append(object_id="urn:uuid:a", event_type="first")
        assert empty_log.next_index == 1
        empty_log.append(object_id="urn:uuid:b", event_type="second")
        assert empty_log.next_index == 2

    def test_returned_entry_matches_stored(self, empty_log: CaseEventLog):
        returned = empty_log.append(object_id=OBJECT_ID, event_type="test")
        stored = empty_log.entries[0]
        assert returned is stored

    def test_rejected_entry_requires_reason_code(
        self, empty_log: CaseEventLog
    ):
        with pytest.raises(ValueError, match="reason_code"):
            empty_log.append(
                object_id=OBJECT_ID,
                event_type="test",
                disposition="rejected",
            )

    def test_rejected_entry_with_reason_code_succeeds(
        self, empty_log: CaseEventLog
    ):
        entry = empty_log.append(
            object_id=OBJECT_ID,
            event_type="test",
            disposition="rejected",
            reason_code="PRECONDITION_FAILED",
        )
        assert entry.disposition == "rejected"


# ---------------------------------------------------------------------------
# CaseEventLog — append-only enforcement
# ---------------------------------------------------------------------------


class TestCaseEventLogAppendOnly:
    def test_entries_returns_tuple(self, log_with_one_entry: CaseEventLog):
        assert isinstance(log_with_one_entry.entries, tuple)

    def test_entries_tuple_is_immutable(
        self, log_with_one_entry: CaseEventLog
    ):
        entries = log_with_one_entry.entries
        with pytest.raises((TypeError, AttributeError)):
            entries[0] = None  # type: ignore[index]

    def test_adding_to_entries_tuple_does_not_affect_log(
        self, empty_log: CaseEventLog
    ):
        """Mutating the returned tuple does not affect the underlying log."""
        empty_log.append(object_id="urn:uuid:a", event_type="first")
        snapshot = empty_log.entries
        assert len(snapshot) == 1
        empty_log.append(object_id="urn:uuid:b", event_type="second")
        # snapshot captured before second append is still length 1
        assert len(snapshot) == 1
        assert len(empty_log.entries) == 2

    def test_case_id_is_read_only(self, empty_log: CaseEventLog):
        with pytest.raises(AttributeError):
            empty_log.case_id = "urn:uuid:modified"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CaseEventLog — recorded_entries projection (CLP-04-001, CLP-04-003)
# ---------------------------------------------------------------------------


class TestCaseEventLogRecordedProjection:
    def test_all_recorded_by_default(
        self, log_with_three_entries: CaseEventLog
    ):
        assert len(log_with_three_entries.recorded_entries) == 3

    def test_rejected_entry_excluded_from_recorded(
        self, empty_log: CaseEventLog
    ):
        empty_log.append(object_id="urn:uuid:a", event_type="first")
        empty_log.append(
            object_id="urn:uuid:b",
            event_type="second",
            disposition="rejected",
            reason_code="PRECONDITION_FAILED",
        )
        empty_log.append(object_id="urn:uuid:c", event_type="third")
        assert len(empty_log.entries) == 3
        assert len(empty_log.recorded_entries) == 2
        assert all(
            e.disposition == "recorded" for e in empty_log.recorded_entries
        )

    def test_tail_hash_skips_rejected_entries(self, empty_log: CaseEventLog):
        e1 = empty_log.append(object_id="urn:uuid:a", event_type="first")
        empty_log.append(
            object_id="urn:uuid:b",
            event_type="rejected_event",
            disposition="rejected",
            reason_code="ERR",
        )
        # tail_hash should still equal e1.entry_hash (last *recorded*)
        assert empty_log.tail_hash == e1.entry_hash

    def test_recorded_entries_is_tuple(self, log_with_one_entry: CaseEventLog):
        assert isinstance(log_with_one_entry.recorded_entries, tuple)


# ---------------------------------------------------------------------------
# CaseEventLog — hash chain verification (SYNC-07-001)
# ---------------------------------------------------------------------------


class TestCaseEventLogVerifyChain:
    def test_empty_log_chain_valid(self, empty_log: CaseEventLog):
        assert empty_log.verify_chain()

    def test_single_entry_chain_valid(self, log_with_one_entry: CaseEventLog):
        assert log_with_one_entry.verify_chain()

    def test_three_entry_chain_valid(
        self, log_with_three_entries: CaseEventLog
    ):
        assert log_with_three_entries.verify_chain()

    def test_tampered_entry_hash_fails_verify_chain(
        self, log_with_one_entry: CaseEventLog
    ):
        tampered = log_with_one_entry._entries[0]
        # Tamper with the stored hash to simulate corruption
        object.__setattr__(tampered, "entry_hash", "deadbeef" * 8)
        assert not log_with_one_entry.verify_chain()

    def test_tampered_prev_hash_fails_verify_chain(
        self, empty_log: CaseEventLog
    ):
        empty_log.append(object_id="urn:uuid:a", event_type="first")
        e2 = empty_log.append(object_id="urn:uuid:b", event_type="second")
        # Tamper with e2's prev_log_hash to point at something wrong
        object.__setattr__(e2, "prev_log_hash", GENESIS_HASH)
        # verify_chain should detect the broken link
        assert not empty_log.verify_chain()

    def test_all_entry_hashes_unique(
        self, log_with_three_entries: CaseEventLog
    ):
        hashes = [e.entry_hash for e in log_with_three_entries.entries]
        assert len(set(hashes)) == len(hashes)


# ---------------------------------------------------------------------------
# ReplicationState
# ---------------------------------------------------------------------------


class TestReplicationState:
    def test_construction_with_peer_id(self):
        peer = "https://example.org/vendor"
        state = ReplicationState(peer_id=peer)
        assert state.peer_id == peer

    def test_default_last_acknowledged_hash_is_genesis(self):
        state = ReplicationState(peer_id="https://example.org/finder")
        assert state.last_acknowledged_hash == GENESIS_HASH

    def test_custom_last_acknowledged_hash(self):
        digest = "a" * 64
        state = ReplicationState(
            peer_id="https://example.org/finder",
            last_acknowledged_hash=digest,
        )
        assert state.last_acknowledged_hash == digest

    def test_updated_at_is_set(self):
        state = ReplicationState(peer_id="https://example.org/finder")
        assert state.updated_at is not None

    def test_pydantic_serialisation_round_trip(self):
        state = ReplicationState(peer_id="https://example.org/finder")
        dumped = state.model_dump()
        restored = ReplicationState.model_validate(dumped)
        assert restored.peer_id == state.peer_id
        assert restored.last_acknowledged_hash == state.last_acknowledged_hash


# ---------------------------------------------------------------------------
# BTBridge — leadership guard (SYNC-09-003)
# ---------------------------------------------------------------------------


class TestBTBridgeLeadershipGuard:
    """Tests for the is_leader port added by SYNC-09-003."""

    def _make_bridge(self, is_leader_fn=None) -> BTBridge:
        dl = MagicMock()
        if is_leader_fn is not None:
            return BTBridge(datalayer=dl, is_leader=is_leader_fn)
        return BTBridge(datalayer=dl)

    def test_default_is_leader_returns_true(self):
        bridge = self._make_bridge()
        assert bridge.is_leader() is True

    def test_custom_is_leader_false_skips_execution(self):
        bridge = self._make_bridge(is_leader_fn=lambda: False)
        dummy_tree = py_trees.behaviours.Success(name="noop")
        result = bridge.execute_with_setup(
            tree=dummy_tree,
            actor_id="urn:uuid:actor1",
        )
        from py_trees.common import Status

        assert result.status == Status.FAILURE
        assert "not the replication leader" in result.feedback_message

    def test_custom_is_leader_true_executes_normally(self):
        """When is_leader() returns True, the tree executes normally."""
        bridge = self._make_bridge(is_leader_fn=lambda: True)
        dummy_tree = py_trees.behaviours.Success(name="noop")
        result = bridge.execute_with_setup(
            tree=dummy_tree,
            actor_id="urn:uuid:actor1",
        )
        from py_trees.common import Status

        assert result.status == Status.SUCCESS

    def test_bridge_without_explicit_is_leader_executes_normally(self):
        """Omitting is_leader defaults to always-True (single-node behaviour)."""
        bridge = self._make_bridge()
        dummy_tree = py_trees.behaviours.Success(name="noop")
        result = bridge.execute_with_setup(
            tree=dummy_tree,
            actor_id="urn:uuid:actor1",
        )
        from py_trees.common import Status

        assert result.status == Status.SUCCESS
