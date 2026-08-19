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

"""Tests for per-activity outbox attempt counter and dead-letter store.

Covers SqliteDataLayer methods added for OX-13-001 through OX-13-004:
- get_outbox_attempt_count / set_outbox_attempt_count / clear_outbox_attempt_count
- dead_letter_append / dead_letter_list

Fixtures ``dl`` and ``scoped_dl`` come from conftest.py.
"""

import pytest

_ALICE = "https://example.org/actors/alice"
_BOB = "https://example.org/actors/bob"
_ACT_ID = "urn:test:activity-001"


@pytest.fixture
def alice_dl(dl):
    """Actor-scoped DL sharing the same engine as *dl* (for read-back tests)."""
    return dl.clone_for_actor(_ALICE)


# ---------------------------------------------------------------------------
# Attempt counter — AC-1 (OX-13-001)
# ---------------------------------------------------------------------------


def test_get_outbox_attempt_count_default_zero(alice_dl):
    """Attempt count starts at 0 for an unseen activity."""
    assert alice_dl.get_outbox_attempt_count(_ACT_ID) == 0


def test_set_and_get_outbox_attempt_count(alice_dl):
    """set_outbox_attempt_count persists the value returned by get."""
    alice_dl.set_outbox_attempt_count(_ACT_ID, 5)
    assert alice_dl.get_outbox_attempt_count(_ACT_ID) == 5


def test_set_outbox_attempt_count_upsert(alice_dl):
    """Setting the count twice keeps only the latest value."""
    alice_dl.set_outbox_attempt_count(_ACT_ID, 3)
    alice_dl.set_outbox_attempt_count(_ACT_ID, 7)
    assert alice_dl.get_outbox_attempt_count(_ACT_ID) == 7


def test_clear_outbox_attempt_count_resets_to_zero(alice_dl):
    """clear_outbox_attempt_count makes the count return 0 again."""
    alice_dl.set_outbox_attempt_count(_ACT_ID, 5)
    alice_dl.clear_outbox_attempt_count(_ACT_ID)
    assert alice_dl.get_outbox_attempt_count(_ACT_ID) == 0


def test_clear_outbox_attempt_count_noop_if_absent(alice_dl):
    """clear_outbox_attempt_count is safe to call when no count is recorded."""
    alice_dl.clear_outbox_attempt_count(_ACT_ID)  # should not raise
    assert alice_dl.get_outbox_attempt_count(_ACT_ID) == 0


def test_attempt_counts_are_actor_scoped(dl):
    """Attempt counts for different actors are independent."""
    actor_a = dl.clone_for_actor(_ALICE)
    actor_b = dl.clone_for_actor(_BOB)

    actor_a.set_outbox_attempt_count(_ACT_ID, 5)
    assert actor_b.get_outbox_attempt_count(_ACT_ID) == 0


def test_attempt_count_distinct_per_activity(alice_dl):
    """Different activity IDs maintain independent counters."""
    act2 = "urn:test:activity-002"
    alice_dl.set_outbox_attempt_count(_ACT_ID, 3)
    alice_dl.set_outbox_attempt_count(act2, 7)
    assert alice_dl.get_outbox_attempt_count(_ACT_ID) == 3
    assert alice_dl.get_outbox_attempt_count(act2) == 7


# ---------------------------------------------------------------------------
# Dead-letter store — AC-2/AC-4 (OX-13-002, OX-13-004)
# ---------------------------------------------------------------------------


def test_dead_letter_list_initially_empty(dl):
    """dead_letter_list returns [] before any entries are appended."""
    assert dl.dead_letter_list() == []


def test_dead_letter_append_and_list(alice_dl, dl):
    """dead_letter_append writes a record readable via dead_letter_list."""
    alice_dl.dead_letter_append(
        _ACT_ID,
        reason="max_attempts_exhausted",
        total_attempts=12,
        failed_recipients=[_BOB],
    )
    entries = dl.dead_letter_list()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.activity_id == _ACT_ID
    assert entry.reason == "max_attempts_exhausted"
    assert entry.total_attempts == 12
    assert _BOB in entry.failed_recipients


def test_dead_letter_entry_carries_actor_id(alice_dl, dl):
    """dead_letter_append records the actor that owned the failing outbox."""
    alice_dl.dead_letter_append(
        _ACT_ID,
        reason="max_attempts_exhausted",
        total_attempts=12,
        failed_recipients=[],
    )
    entries = dl.dead_letter_list()
    assert entries[0].actor_id == _ALICE


def test_dead_letter_list_multiple_entries(dl):
    """dead_letter_list returns all entries regardless of originating actor."""
    for i in range(3):
        actor = dl.clone_for_actor(f"https://example.org/actors/actor-{i}")
        actor.dead_letter_append(
            f"urn:test:activity-{i}",
            reason="max_attempts_exhausted",
            total_attempts=12,
            failed_recipients=[],
        )
    assert len(dl.dead_letter_list()) == 3


def test_dead_letter_entry_has_timestamp(alice_dl, dl):
    """Each dead-letter entry carries a recorded_at timestamp."""
    alice_dl.dead_letter_append(
        _ACT_ID,
        reason="max_attempts_exhausted",
        total_attempts=12,
        failed_recipients=[],
    )
    entry = dl.dead_letter_list()[0]
    assert entry.recorded_at is not None
