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

Retry bookkeeping is *per actor* (ADR-0066): an attempt counter and a
dead-letter entry both describe one actor's own failed delivery, so they live in
that actor's store.  Each test therefore reads back from the same store it wrote
to.  These tests originally read back through a second DataLayer on the
assumption that ``clone_for_actor`` shared an engine; it does not, because a
clone is a *different actor's store*.
"""

import pytest

_ALICE = "https://example.org/actors/alice"
_BOB = "https://example.org/actors/bob"
_ACT_ID = "urn:test:activity-001"


@pytest.fixture
def alice_dl(dl):
    """Alice's own store, reached from *dl* via the named cross-actor route."""
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


def test_dead_letter_append_and_list(alice_dl):
    """dead_letter_append writes a record readable via dead_letter_list."""
    alice_dl.dead_letter_append(
        _ACT_ID,
        reason="max_attempts_exhausted",
        total_attempts=12,
        failed_recipients=[_BOB],
    )
    entries = alice_dl.dead_letter_list()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.activity_id == _ACT_ID
    assert entry.reason == "max_attempts_exhausted"
    assert entry.total_attempts == 12
    assert _BOB in entry.failed_recipients


def test_dead_letter_entry_carries_actor_id(alice_dl):
    """dead_letter_append records the actor that owned the failing outbox.

    The store already fixes whose outbox this was, so ``actor_id`` is not an
    argument — it is read off the DataLayer.  The field survives because a
    fanned-out operator view needs each entry to name its origin once the
    entries are pooled outside their stores.
    """
    alice_dl.dead_letter_append(
        _ACT_ID,
        reason="max_attempts_exhausted",
        total_attempts=12,
        failed_recipients=[],
    )
    entries = alice_dl.dead_letter_list()
    assert entries[0].actor_id == _ALICE


def test_dead_letter_list_is_actor_scoped(dl):
    """Each actor's dead-letter list holds only that actor's entries.

    This replaces a test that asserted ``dead_letter_list`` "returns all
    entries regardless of originating actor" — true of the shared pool it was
    written against, and made impossible by ADR-0066.  A node-wide operator
    view is an explicit fan-out over hosted actors, which is what the second
    half of this test performs.
    """
    actor_ids = [f"https://example.org/actors/actor-{i}" for i in range(3)]
    for i, actor_id in enumerate(actor_ids):
        actor = dl.clone_for_actor(actor_id)
        actor.dead_letter_append(
            f"urn:test:activity-{i}",
            reason="max_attempts_exhausted",
            total_attempts=12,
            failed_recipients=[],
        )

    # No actor sees another's entry, and the store the clones were made from
    # sees none of them.
    for i, actor_id in enumerate(actor_ids):
        entries = dl.clone_for_actor(actor_id).dead_letter_list()
        assert [e.activity_id for e in entries] == [f"urn:test:activity-{i}"]
    assert dl.dead_letter_list() == []

    # The node-wide view is assembled, not queried.
    pooled = [
        entry
        for actor_id in actor_ids
        for entry in dl.clone_for_actor(actor_id).dead_letter_list()
    ]
    assert len(pooled) == 3
    assert {e.actor_id for e in pooled} == set(actor_ids)


def test_dead_letter_entry_has_timestamp(alice_dl):
    """Each dead-letter entry carries a recorded_at timestamp."""
    alice_dl.dead_letter_append(
        _ACT_ID,
        reason="max_attempts_exhausted",
        total_attempts=12,
        failed_recipients=[],
    )
    entry = alice_dl.dead_letter_list()[0]
    assert entry.recorded_at is not None


def test_dead_letter_list_skips_corrupted_entries(
    alice_dl, dl, caplog, monkeypatch
):
    """dead_letter_list silently skips undeserializable entries and returns valid ones."""
    from datetime import UTC, datetime

    valid_data = {
        "type_": "OutboxDeadLetterEntry",
        "id_": "urn:test:valid-dl-entry",
        "activity_id": _ACT_ID,
        "actor_id": _ALICE,
        "reason": "max_attempts_exhausted",
        "total_attempts": 12,
        "failed_recipients": [],
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    corrupted_data = {
        "type_": "OutboxDeadLetterEntry"
    }  # missing required fields

    monkeypatch.setattr(
        dl,
        "by_type",
        lambda _type: {"id-valid": valid_data, "id-corrupt": corrupted_data},
    )

    import logging

    with caplog.at_level(logging.WARNING):
        entries = dl.dead_letter_list()

    assert len(entries) == 1
    assert entries[0].activity_id == _ACT_ID
    assert "could not reconstruct" in caplog.text
