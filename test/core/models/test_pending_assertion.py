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
- timeout expiry on a write or a sweep, never on a lookup (#5591)
- zero timeout disables suppression entirely
- configurable timeout override
- module-level registry (get_pending_assertion_store, reset_pending_assertion_stores)
- expire_timed_out sweep helper

Spec: SYNC-07-001 through SYNC-07-005.
"""

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from vultron.core.models._helpers import now_utc
from vultron.core.models.pending_assertion import (
    DEFAULT_PENDING_ASSERTION_TIMEOUT,
    PendingAssertion,
    PendingAssertionStore,
    ProtocolPair,
    get_pending_assertion_store,
    record_pending_assertion,
    reset_pending_assertion_stores,
)
from vultron.demo.determinism import deterministic_run

CASE_ID = "https://example.org/cases/case-001"
SEMANTIC_TYPE = "submit_report"
OBJECT_ID = "https://example.org/activities/act-001"
OTHER_OBJECT_ID = "https://example.org/activities/act-002"
SUBJECT_ID = "https://example.org/cases/case-001/embargo_events/e1"

#: The store key of the ``(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)`` entry.
_KEY = ProtocolPair(
    case_id=CASE_ID,
    request_semantic_type=SEMANTIC_TYPE,
    object_id=OBJECT_ID,
)

ACTOR_A = "https://example.org/actors/alice"
ACTOR_B = "https://example.org/actors/bob"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_registry():
    """Prevent cross-test leakage in the module-level store registry."""
    reset_pending_assertion_stores()
    yield
    reset_pending_assertion_stores()


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
            case_id=CASE_ID, semantic_type=SEMANTIC_TYPE, object_id=OBJECT_ID
        )
        assert entry.status == "pending"

    def test_emitted_at_is_recent_utc(self):
        before = now_utc()
        entry = PendingAssertion(
            case_id=CASE_ID, semantic_type=SEMANTIC_TYPE, object_id=OBJECT_ID
        )
        after = now_utc()
        assert before <= entry.emitted_at <= after

    def test_status_can_be_overridden(self):
        entry = PendingAssertion(
            case_id=CASE_ID,
            semantic_type=SEMANTIC_TYPE,
            object_id=OBJECT_ID,
            status="cleared",
        )
        assert entry.status == "cleared"


# ---------------------------------------------------------------------------
# PendingAssertionStore — add / is_suppressed
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-07-004")
class TestAddAndIsSuppress:
    def test_new_store_does_not_suppress(self, store):
        assert not store.is_suppressed(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

    def test_add_then_is_suppressed(self, store):
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        assert store.is_suppressed(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

    def test_different_case_id_not_suppressed(self, store):
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        assert not store.is_suppressed(
            "https://example.org/cases/case-002", SEMANTIC_TYPE, OBJECT_ID
        )

    def test_different_semantic_type_not_suppressed(self, store):
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        assert not store.is_suppressed(CASE_ID, "engage_case", OBJECT_ID)

    def test_different_object_id_not_suppressed(self, store):
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        assert not store.is_suppressed(
            CASE_ID,
            SEMANTIC_TYPE,
            "https://example.org/activities/act-999",
        )

    def test_len_increases_on_add(self, store):
        assert len(store) == 0
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        assert len(store) == 1


# ---------------------------------------------------------------------------
# PendingAssertionStore — clear
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_prevents_suppression(self, store):
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        store.clear(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        assert not store.is_suppressed(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

    def test_clear_sets_status_cleared(self, store):
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        store.clear(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        key = ProtocolPair(
            case_id=CASE_ID,
            request_semantic_type=SEMANTIC_TYPE,
            object_id=OBJECT_ID,
        )
        assert store._store[key].status == "cleared"

    def test_clear_on_nonexistent_is_noop(self, store):
        # Should not raise
        store.clear(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

    def test_clear_on_already_cleared_is_noop(self, store):
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        store.clear(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        store.clear(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)  # second clear
        key = ProtocolPair(
            case_id=CASE_ID,
            request_semantic_type=SEMANTIC_TYPE,
            object_id=OBJECT_ID,
        )
        assert store._store[key].status == "cleared"

    def test_cleared_entry_does_not_suppress_future_add(self, store):
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        store.clear(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        # A new add should reset suppression
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        assert store.is_suppressed(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)


# ---------------------------------------------------------------------------
# PendingAssertionStore — timeout
# ---------------------------------------------------------------------------


class TestTimeout:
    """The timeout is applied on a write or a sweep, never on a lookup (#5591).

    Under the demo recording clock a read costs a tick, so a lookup that read
    the clock moved every later timestamp in the recording when it raced
    another thread.  An entry that has aged out must still time out
    (SYNC-11-005), so each test below drives the expiry through the write or
    the sweep that sees the time pass.
    """

    def test_a_sweep_stops_an_aged_out_entry_suppressing(self, store_short):
        """is_suppressed returns False once a sweep has seen the timeout pass."""
        store_short.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

        # Simulate time passing beyond the 60-second window
        future = datetime.now(UTC) + timedelta(seconds=61)
        with patch("vultron.core.models._helpers.datetime") as mock_dt:
            mock_dt.now.return_value = future
            store_short.expire_timed_out()

        assert not store_short.is_suppressed(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

    def test_a_later_write_stops_an_aged_out_entry_suppressing(
        self, store_short
    ):
        """The instant a new entry carries expires the entries it outlived.

        An actor that asserts anything at all sweeps as it goes, so no sweep
        call is needed for the ask that follows another one.
        """
        store_short.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

        future = datetime.now(UTC) + timedelta(seconds=61)
        with patch("vultron.core.models._helpers.datetime") as mock_dt:
            mock_dt.now.return_value = future
            store_short.add(CASE_ID, "engage_case", OTHER_OBJECT_ID)

        assert not store_short.is_suppressed(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        assert store_short.is_suppressed(
            CASE_ID, "engage_case", OTHER_OBJECT_ID
        )

    def test_an_aged_out_entry_status_becomes_timed_out(self, store_short):
        store_short.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

        future = datetime.now(UTC) + timedelta(seconds=61)
        with patch("vultron.core.models._helpers.datetime") as mock_dt:
            mock_dt.now.return_value = future
            store_short.expire_timed_out()

        assert store_short._store[_KEY].status == "timed_out"

    def test_a_lookup_leaves_an_aged_out_entry_pending(self, store_short):
        """A lookup marks nothing: that is what keeps it clock-free (#5591).

        The entry still suppresses until a write or a sweep sees the time
        pass, which is why :meth:`expire_timed_out` is what SYNC-11-005's
        operator retry calls before it resubmits.
        """
        store_short.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

        future = datetime.now(UTC) + timedelta(seconds=61)
        with patch("vultron.core.models._helpers.datetime") as mock_dt:
            mock_dt.now.return_value = future
            suppressed = store_short.is_suppressed(
                CASE_ID, SEMANTIC_TYPE, OBJECT_ID
            )

        assert suppressed
        assert store_short._store[_KEY].status == "pending"

    def test_a_lookup_reads_no_clock(self):
        """Every lookup leaves the recording clock where it found it (AC-1).

        Measured the way the DataLayer read paths are (#5510): a seeded run
        mints the same next instant whether or not the lookups ran.
        """
        subject_lookups = 5

        def next_instant(lookups: int) -> datetime:
            with deterministic_run("pending-assertion-lookup"):
                store = PendingAssertionStore()
                store.add(
                    CASE_ID, SEMANTIC_TYPE, OBJECT_ID, subject_id=SUBJECT_ID
                )
                for _ in range(lookups):
                    assert store.is_suppressed(
                        CASE_ID, SEMANTIC_TYPE, OBJECT_ID
                    )
                    assert (
                        store.pending_for_subject(
                            CASE_ID, SEMANTIC_TYPE, SUBJECT_ID
                        )
                        is not None
                    )
                    assert store.clear_activity(CASE_ID, OTHER_OBJECT_ID) == []
                return now_utc()

        assert next_instant(subject_lookups) == next_instant(0)

    def test_an_unexpired_entry_still_suppresses_after_a_sweep(
        self, store_short
    ):
        store_short.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        future = datetime.now(UTC) + timedelta(seconds=30)
        with patch("vultron.core.models._helpers.datetime") as mock_dt:
            mock_dt.now.return_value = future
            assert store_short.expire_timed_out() == 0

        assert store_short.is_suppressed(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

    def test_timed_out_entry_logs_error(self, store_short, caplog):
        store_short.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        future = datetime.now(UTC) + timedelta(seconds=61)
        with caplog.at_level(
            logging.ERROR,
            logger="vultron.core.models.pending_assertion",
        ):
            with patch("vultron.core.models._helpers.datetime") as mock_dt:
                mock_dt.now.return_value = future
                store_short.expire_timed_out()

        assert any("timed out" in r.message for r in caplog.records)

    def test_timed_out_entry_allows_subsequent_add(self, store_short):
        store_short.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        future = datetime.now(UTC) + timedelta(seconds=61)
        with patch("vultron.core.models._helpers.datetime") as mock_dt:
            mock_dt.now.return_value = future
            # expire the entry
            store_short.expire_timed_out()

        # A fresh add should work and suppress again
        store_short.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        assert store_short.is_suppressed(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

    def test_a_sweep_at_an_earlier_instant_expires_nothing_new(
        self, store_short
    ):
        """The observed instant only moves forward (a peer clock running back)."""
        store_short.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        future = datetime.now(UTC) + timedelta(seconds=61)
        past = datetime.now(UTC) - timedelta(seconds=600)
        with patch("vultron.core.models._helpers.datetime") as mock_dt:
            mock_dt.now.return_value = future
            assert store_short.expire_timed_out() == 1
            mock_dt.now.return_value = past
            assert store_short.expire_timed_out() == 0

        assert store_short._store[_KEY].status == "timed_out"


# ---------------------------------------------------------------------------
# PendingAssertionStore — zero timeout disables suppression
# ---------------------------------------------------------------------------


class TestZeroTimeout:
    def test_add_then_not_suppressed_with_zero_timeout(self, store_zero):
        store_zero.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        assert not store_zero.is_suppressed(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

    def test_zero_timeout_always_returns_false(self, store_zero):
        assert not store_zero.is_suppressed(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)


# ---------------------------------------------------------------------------
# PendingAssertionStore — expire_timed_out sweep
# ---------------------------------------------------------------------------


class TestExpireTimedOut:
    def test_sweep_returns_zero_when_nothing_expired(self, store_short):
        store_short.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        assert store_short.expire_timed_out() == 0

    def test_sweep_returns_count_of_expired_entries(self, store_short):
        store_short.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        store_short.add(
            CASE_ID,
            "engage_case",
            "https://example.org/activities/act-002",
        )
        future = datetime.now(UTC) + timedelta(seconds=61)
        with patch("vultron.core.models._helpers.datetime") as mock_dt:
            mock_dt.now.return_value = future
            count = store_short.expire_timed_out()
        assert count == 2

    def test_sweep_skips_already_cleared(self, store_short):
        store_short.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        store_short.clear(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        future = datetime.now(UTC) + timedelta(seconds=61)
        with patch("vultron.core.models._helpers.datetime") as mock_dt:
            mock_dt.now.return_value = future
            count = store_short.expire_timed_out()
        assert count == 0


# ---------------------------------------------------------------------------
# Module-level registry
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-07-005")
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
        sa.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

        sb = get_pending_assertion_store(ACTOR_B)
        assert not sb.is_suppressed(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

    def test_reset_stores_clears_registry(self):
        s1 = get_pending_assertion_store(ACTOR_A)
        reset_pending_assertion_stores()
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


# ---------------------------------------------------------------------------
# pending_for_subject — duplicate check keyed by subject (SYNC-11-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-11-002")
class TestPendingForSubject:
    def test_pending_entry_matches_its_subject(self, store):
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID, subject_id=SUBJECT_ID)
        entry = store.pending_for_subject(CASE_ID, SEMANTIC_TYPE, SUBJECT_ID)
        assert entry is not None
        assert entry.object_id == OBJECT_ID

    def test_zero_timeout_never_matches(self, store_zero):
        store_zero.add(
            CASE_ID, SEMANTIC_TYPE, OBJECT_ID, subject_id=SUBJECT_ID
        )
        assert (
            store_zero.pending_for_subject(CASE_ID, SEMANTIC_TYPE, SUBJECT_ID)
            is None
        )

    def test_a_swept_entry_times_out_and_no_longer_matches(self, store_short):
        store_short.add(
            CASE_ID, SEMANTIC_TYPE, OBJECT_ID, subject_id=SUBJECT_ID
        )
        future = datetime.now(UTC) + timedelta(seconds=61)
        with patch("vultron.core.models._helpers.datetime") as mock_dt:
            mock_dt.now.return_value = future
            store_short.expire_timed_out()

        assert (
            store_short.pending_for_subject(CASE_ID, SEMANTIC_TYPE, SUBJECT_ID)
            is None
        )
        assert store_short._store[_KEY].status == "timed_out"

    def test_cleared_entry_does_not_match(self, store):
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID, subject_id=SUBJECT_ID)
        store.clear(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        assert (
            store.pending_for_subject(CASE_ID, SEMANTIC_TYPE, SUBJECT_ID)
            is None
        )

    @pytest.mark.parametrize(
        ("case_id", "semantic_type", "subject_id"),
        [
            ("https://example.org/cases/other", SEMANTIC_TYPE, SUBJECT_ID),
            (CASE_ID, "other_event", SUBJECT_ID),
            (CASE_ID, SEMANTIC_TYPE, "https://example.org/other-subject"),
        ],
        ids=["other-case", "other-semantic-type", "other-subject"],
    )
    def test_mismatch_does_not_match(
        self, store, case_id, semantic_type, subject_id
    ):
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID, subject_id=SUBJECT_ID)
        assert (
            store.pending_for_subject(case_id, semantic_type, subject_id)
            is None
        )


@pytest.mark.spec("SYNC-11-002")
def test_record_pending_assertion_records_in_the_actors_store():
    record_pending_assertion(
        ACTOR_A, CASE_ID, SEMANTIC_TYPE, OBJECT_ID, subject_id=SUBJECT_ID
    )
    store = get_pending_assertion_store(ACTOR_A)
    assert store.is_suppressed(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
    assert (
        store.pending_for_subject(CASE_ID, SEMANTIC_TYPE, SUBJECT_ID)
        is not None
    )
    assert len(get_pending_assertion_store(ACTOR_B)) == 0


class TestClearActivity:
    """A refusal notice names the activity, not its semantic type (CLP-06-006)."""

    @pytest.mark.spec("CLP-06-006")
    def test_clears_the_pending_entry_for_the_activity(self):
        store = PendingAssertionStore()
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

        cleared = store.clear_activity(CASE_ID, OBJECT_ID)

        assert [e.object_id for e in cleared] == [OBJECT_ID]
        assert not store.is_suppressed(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

    def test_leaves_other_activities_and_cases_pending(self):
        store = PendingAssertionStore()
        other = "https://example.org/activities/act-002"
        other_case = "https://example.org/cases/case-002"
        store.add(CASE_ID, SEMANTIC_TYPE, other)
        store.add(other_case, SEMANTIC_TYPE, OBJECT_ID)

        assert store.clear_activity(CASE_ID, OBJECT_ID) == []
        assert store.is_suppressed(CASE_ID, SEMANTIC_TYPE, other)
        assert store.is_suppressed(other_case, SEMANTIC_TYPE, OBJECT_ID)

    def test_an_already_cleared_entry_is_not_cleared_again(self):
        store = PendingAssertionStore()
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        store.clear_activity(CASE_ID, OBJECT_ID)

        assert store.clear_activity(CASE_ID, OBJECT_ID) == []

    def test_a_timed_out_entry_is_not_cleared(self):
        store = PendingAssertionStore(timeout_seconds=10)
        store.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)
        later = datetime.now(UTC) + timedelta(seconds=11)

        with patch("vultron.core.models._helpers.datetime") as mock_dt:
            mock_dt.now.return_value = later
            store.expire_timed_out()
        cleared = store.clear_activity(CASE_ID, OBJECT_ID)

        assert cleared == []
        entry = next(iter(store._store.values()))
        assert entry.status == "timed_out"

    def test_a_zero_timeout_store_clears_its_entry(self, store_zero):
        store_zero.add(CASE_ID, SEMANTIC_TYPE, OBJECT_ID)

        cleared = store_zero.clear_activity(CASE_ID, OBJECT_ID)

        assert [e.object_id for e in cleared] == [OBJECT_ID]
        assert cleared[0].status == "cleared"
