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
"""Unit tests for PendingAssertion and PendingAssertionStore.

Covers:
- add / is_suppressed / clear semantics
- timeout expiry (status → timed_out, no suppression after)
- zero timeout disables suppression entirely
- configurable timeout override
- module-level registry (get_pending_assertion_store, _reset_stores)
- expire_timed_out sweep helper

Spec: SYNC-07-001 through SYNC-07-005.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from vultron.core.models.pending_assertion import (
    DEFAULT_PENDING_ASSERTION_TIMEOUT,
    PendingAssertion,
    PendingAssertionStore,
    ProtocolPair,
    _reset_stores,
    get_pending_assertion_store,
)

CASE_ID = "https://example.org/cases/case-001"
EVENT_TYPE = "submit_report"
OBJECT_ID = "https://example.org/activities/act-001"

ACTOR_A = "https://example.org/actors/alice"
ACTOR_B = "https://example.org/actors/bob"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_registry():
    """Prevent cross-test leakage in the module-level store registry."""
    _reset_stores()
    yield
    _reset_stores()


@pytest.fixture
def store() -> PendingAssertionStore:
    return PendingAssertionStore()


@pytest.fixture
def store_zero() -> PendingAssertionStore:
    """Store with zero timeout — suppression disabled."""
    return PendingAssertionStore(timeout_seconds=0)


@pytest.fixture
def store_short() -> PendingAssertionStore:
    """Store with a 60-second timeout for timeout tests."""
    return PendingAssertionStore(timeout_seconds=60)


# ---------------------------------------------------------------------------
# PendingAssertion dataclass
# ---------------------------------------------------------------------------


class TestPendingAssertionDataclass:
    def test_default_status_is_pending(self):
        entry = PendingAssertion(
            case_id=CASE_ID, event_type=EVENT_TYPE, object_id=OBJECT_ID
        )
        assert entry.status == "pending"

    def test_emitted_at_is_recent_utc(self):
        before = datetime.now(timezone.utc)
        entry = PendingAssertion(
            case_id=CASE_ID, event_type=EVENT_TYPE, object_id=OBJECT_ID
        )
        after = datetime.now(timezone.utc)
        assert before <= entry.emitted_at <= after

    def test_status_can_be_overridden(self):
        entry = PendingAssertion(
            case_id=CASE_ID,
            event_type=EVENT_TYPE,
            object_id=OBJECT_ID,
            status="cleared",
        )
        assert entry.status == "cleared"


# ---------------------------------------------------------------------------
# PendingAssertionStore — add / is_suppressed
# ---------------------------------------------------------------------------


class TestAddAndIsSuppress:
    def test_new_store_does_not_suppress(self, store):
        assert not store.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)

    def test_add_then_is_suppressed(self, store):
        store.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        assert store.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)

    def test_different_case_id_not_suppressed(self, store):
        store.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        assert not store.is_suppressed(
            "https://example.org/cases/case-002", EVENT_TYPE, OBJECT_ID
        )

    def test_different_event_type_not_suppressed(self, store):
        store.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        assert not store.is_suppressed(CASE_ID, "engage_case", OBJECT_ID)

    def test_different_object_id_not_suppressed(self, store):
        store.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        assert not store.is_suppressed(
            CASE_ID,
            EVENT_TYPE,
            "https://example.org/activities/act-999",
        )

    def test_len_increases_on_add(self, store):
        assert len(store) == 0
        store.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        assert len(store) == 1


# ---------------------------------------------------------------------------
# PendingAssertionStore — clear
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_prevents_suppression(self, store):
        store.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        store.clear(CASE_ID, EVENT_TYPE, OBJECT_ID)
        assert not store.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)

    def test_clear_sets_status_cleared(self, store):
        store.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        store.clear(CASE_ID, EVENT_TYPE, OBJECT_ID)
        key = ProtocolPair(
            case_id=CASE_ID, request_event_type=EVENT_TYPE, object_id=OBJECT_ID
        )
        assert store._store[key].status == "cleared"

    def test_clear_on_nonexistent_is_noop(self, store):
        # Should not raise
        store.clear(CASE_ID, EVENT_TYPE, OBJECT_ID)

    def test_clear_on_already_cleared_is_noop(self, store):
        store.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        store.clear(CASE_ID, EVENT_TYPE, OBJECT_ID)
        store.clear(CASE_ID, EVENT_TYPE, OBJECT_ID)  # second clear
        key = ProtocolPair(
            case_id=CASE_ID, request_event_type=EVENT_TYPE, object_id=OBJECT_ID
        )
        assert store._store[key].status == "cleared"

    def test_cleared_entry_does_not_suppress_future_add(self, store):
        store.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        store.clear(CASE_ID, EVENT_TYPE, OBJECT_ID)
        # A new add should reset suppression
        store.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        assert store.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)


# ---------------------------------------------------------------------------
# PendingAssertionStore — timeout
# ---------------------------------------------------------------------------


class TestTimeout:
    def test_expired_entry_is_not_suppressed(self, store_short):
        """is_suppressed returns False once the timeout has elapsed."""
        store_short.add(CASE_ID, EVENT_TYPE, OBJECT_ID)

        # Simulate time passing beyond the 60-second window
        future = datetime.now(timezone.utc) + timedelta(seconds=61)
        with patch(
            "vultron.core.models.pending_assertion.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = future
            assert not store_short.is_suppressed(
                CASE_ID, EVENT_TYPE, OBJECT_ID
            )

    def test_expired_entry_status_becomes_timed_out(self, store_short):
        store_short.add(CASE_ID, EVENT_TYPE, OBJECT_ID)

        future = datetime.now(timezone.utc) + timedelta(seconds=61)
        with patch(
            "vultron.core.models.pending_assertion.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = future
            store_short.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)

        key = ProtocolPair(
            case_id=CASE_ID, request_event_type=EVENT_TYPE, object_id=OBJECT_ID
        )
        assert store_short._store[key].status == "timed_out"

    def test_timed_out_entry_logs_error(self, store_short, caplog):
        import logging

        store_short.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        future = datetime.now(timezone.utc) + timedelta(seconds=61)
        with caplog.at_level(
            logging.ERROR,
            logger="vultron.core.models.pending_assertion",
        ):
            with patch(
                "vultron.core.models.pending_assertion.datetime"
            ) as mock_dt:
                mock_dt.now.return_value = future
                store_short.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)

        assert any("timed out" in r.message for r in caplog.records)

    def test_unexpired_entry_still_suppresses(self, store_short):
        store_short.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        future = datetime.now(timezone.utc) + timedelta(seconds=30)
        with patch(
            "vultron.core.models.pending_assertion.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = future
            assert store_short.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)

    def test_timed_out_entry_allows_subsequent_add(self, store_short):
        store_short.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        future = datetime.now(timezone.utc) + timedelta(seconds=61)
        with patch(
            "vultron.core.models.pending_assertion.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = future
            # expire the entry
            store_short.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)

        # A fresh add should work and suppress again
        store_short.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        assert store_short.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)


# ---------------------------------------------------------------------------
# PendingAssertionStore — zero timeout disables suppression
# ---------------------------------------------------------------------------


class TestZeroTimeout:
    def test_add_then_not_suppressed_with_zero_timeout(self, store_zero):
        store_zero.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        assert not store_zero.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)

    def test_zero_timeout_always_returns_false(self, store_zero):
        assert not store_zero.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)


# ---------------------------------------------------------------------------
# PendingAssertionStore — expire_timed_out sweep
# ---------------------------------------------------------------------------


class TestExpireTimedOut:
    def test_sweep_returns_zero_when_nothing_expired(self, store_short):
        store_short.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        assert store_short.expire_timed_out() == 0

    def test_sweep_returns_count_of_expired_entries(self, store_short):
        store_short.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        store_short.add(
            CASE_ID,
            "engage_case",
            "https://example.org/activities/act-002",
        )
        future = datetime.now(timezone.utc) + timedelta(seconds=61)
        with patch(
            "vultron.core.models.pending_assertion.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = future
            count = store_short.expire_timed_out()
        assert count == 2

    def test_sweep_skips_already_cleared(self, store_short):
        store_short.add(CASE_ID, EVENT_TYPE, OBJECT_ID)
        store_short.clear(CASE_ID, EVENT_TYPE, OBJECT_ID)
        future = datetime.now(timezone.utc) + timedelta(seconds=61)
        with patch(
            "vultron.core.models.pending_assertion.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = future
            count = store_short.expire_timed_out()
        assert count == 0


# ---------------------------------------------------------------------------
# Module-level registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_get_store_creates_new_for_new_actor(self):
        s = get_pending_assertion_store(ACTOR_A)
        assert isinstance(s, PendingAssertionStore)

    def test_get_store_returns_same_instance(self):
        s1 = get_pending_assertion_store(ACTOR_A)
        s2 = get_pending_assertion_store(ACTOR_A)
        assert s1 is s2

    def test_different_actors_get_different_stores(self):
        sa = get_pending_assertion_store(ACTOR_A)
        sb = get_pending_assertion_store(ACTOR_B)
        assert sa is not sb

    def test_stores_are_isolated_per_actor(self):
        sa = get_pending_assertion_store(ACTOR_A)
        sa.add(CASE_ID, EVENT_TYPE, OBJECT_ID)

        sb = get_pending_assertion_store(ACTOR_B)
        assert not sb.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)

    def test_reset_stores_clears_registry(self):
        s1 = get_pending_assertion_store(ACTOR_A)
        _reset_stores()
        s2 = get_pending_assertion_store(ACTOR_A)
        assert s1 is not s2

    def test_default_timeout_matches_constant(self):
        s = get_pending_assertion_store(ACTOR_A)
        assert s.timeout_seconds == DEFAULT_PENDING_ASSERTION_TIMEOUT

    def test_custom_timeout_applied_on_first_creation(self):
        s = get_pending_assertion_store(ACTOR_A, timeout_seconds=30.0)
        assert s.timeout_seconds == 30.0

    def test_timeout_not_overridden_on_subsequent_calls(self):
        get_pending_assertion_store(ACTOR_A, timeout_seconds=30.0)
        # Second call with different timeout should NOT override
        s = get_pending_assertion_store(ACTOR_A, timeout_seconds=999.0)
        assert s.timeout_seconds == 30.0
