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

"""Tests for SqliteDataLayer inbox/outbox queue operations and enqueue callback.

Covers: inbox_append/list/pop, outbox_append/list/pop, file-backed
integration, set_enqueue_callback, and clone_for_actor.
Fixtures (dl, file_dl, scoped_dl) come from conftest.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

# ---------------------------------------------------------------------------
# Inbox queue methods
# ---------------------------------------------------------------------------


def test_inbox_starts_empty(dl):
    assert dl.inbox_list() == []


def test_inbox_append_and_list(dl):
    dl.inbox_append("https://example.org/activities/001")
    assert "https://example.org/activities/001" in dl.inbox_list()


def test_inbox_pop_fifo_order(dl):
    dl.inbox_append("https://example.org/activities/001")
    dl.inbox_append("https://example.org/activities/002")
    assert dl.inbox_pop() == "https://example.org/activities/001"
    assert len(dl.inbox_list()) == 1


def test_inbox_pop_empty_returns_none(dl):
    assert dl.inbox_pop() is None


# ---------------------------------------------------------------------------
# Outbox queue methods
# ---------------------------------------------------------------------------


def test_outbox_starts_empty(dl):
    assert dl.outbox_list() == []


def test_outbox_append_and_list(dl):
    dl.outbox_append("https://example.org/activities/sent-001")
    assert "https://example.org/activities/sent-001" in dl.outbox_list()


def test_outbox_pop_fifo_order(dl):
    dl.outbox_append("https://example.org/activities/sent-001")
    dl.outbox_append("https://example.org/activities/sent-002")
    assert dl.outbox_pop() == "https://example.org/activities/sent-001"
    assert len(dl.outbox_list()) == 1


def test_outbox_pop_empty_returns_none(dl):
    assert dl.outbox_pop() is None


# ---------------------------------------------------------------------------
# Outbox-id idempotency check (OX-06-002, ADR-0119)
# ---------------------------------------------------------------------------


@pytest.mark.spec("OX-06-002")
def test_outbox_append_reports_that_it_queued(dl):
    assert dl.outbox_append("urn:test:once") is True
    assert dl.outbox_list() == ["urn:test:once"]


@pytest.mark.spec("OX-06-002")
def test_an_id_already_pending_is_not_queued_again(dl):
    dl.outbox_append("urn:test:first")
    dl.outbox_append("urn:test:retried")
    dl.outbox_append("urn:test:last")

    assert dl.outbox_append("urn:test:retried") is False

    # One row, still in its first place: the retry did not move it.
    assert dl.outbox_list() == [
        "urn:test:first",
        "urn:test:retried",
        "urn:test:last",
    ]


@pytest.mark.spec("OX-06-002")
def test_an_id_no_longer_pending_is_queued_again(dl):
    """Delivery pops the row; the same id is queued again, not lost."""
    dl.outbox_append("urn:test:delivered")
    assert dl.outbox_pop() == "urn:test:delivered"

    assert dl.outbox_append("urn:test:delivered") is True
    assert dl.outbox_list() == ["urn:test:delivered"]


def test_outbox_withdraw_removes_a_pending_id_and_leaves_the_rest(dl):
    """A pending activity can be taken back before delivery (ADR-0119)."""
    dl.outbox_append("urn:test:kept")
    dl.outbox_append("urn:test:withdrawn")

    assert dl.outbox_withdraw("urn:test:withdrawn") is True
    assert dl.outbox_list() == ["urn:test:kept"]


def test_outbox_withdraw_reports_an_id_delivery_already_took(dl):
    dl.outbox_append("urn:test:delivered")
    assert dl.outbox_pop() == "urn:test:delivered"

    assert dl.outbox_withdraw("urn:test:delivered") is False
    assert dl.outbox_withdraw("urn:test:never-queued") is False


@pytest.mark.integration
@pytest.mark.spec("OX-06-002")
def test_concurrent_appends_to_a_file_backed_store_queue_one_row(file_dl):
    """File-backed sessions are not serialized; the one statement still is."""
    import threading

    writers = 8
    barrier = threading.Barrier(writers)
    results: list[bool] = []
    lock = threading.Lock()

    def _append() -> None:
        barrier.wait()
        queued = file_dl.outbox_append("urn:test:raced")
        with lock:
            results.append(queued)

    threads = [threading.Thread(target=_append) for _ in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == [False] * (writers - 1) + [True]
    assert file_dl.outbox_list() == ["urn:test:raced"]


@pytest.mark.spec("OX-06-002")
def test_the_inbox_does_not_take_the_outbox_check(dl):
    """The check is the outbox's: an id in the inbox does not block it."""
    dl.inbox_append("urn:test:shared")
    assert dl.outbox_append("urn:test:shared") is True
    assert dl.inbox_list() == ["urn:test:shared"]


# ---------------------------------------------------------------------------
# UNIQUE index on (queue, activity_id) — AC-3 for issue #4629
# ---------------------------------------------------------------------------


@pytest.mark.spec("OX-06-002")
def test_unique_index_exists_on_queue_entry_table(dl):
    """The vultron_queue table carries a UNIQUE index on (queue, activity_id).

    Asserts the schema-level constraint so that a store-reset note without a
    test would be easy to miss.
    """
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(dl._engine)
    unique_constraints = inspector.get_unique_constraints("vultron_queue")
    # SQLite also surfaces UNIQUE indexes through get_indexes; check both.
    unique_indexes = [
        idx
        for idx in inspector.get_indexes("vultron_queue")
        if idx.get("unique")
    ]
    all_unique_cols = [
        tuple(sorted(uc["column_names"])) for uc in unique_constraints
    ] + [tuple(sorted(idx["column_names"])) for idx in unique_indexes]
    assert ("activity_id", "queue") in all_unique_cols, (
        f"No UNIQUE(queue, activity_id) found on vultron_queue; "
        f"unique_constraints={unique_constraints!r}, "
        f"unique_indexes={unique_indexes!r}"
    )


@pytest.mark.integration
@pytest.mark.spec("OX-06-002")
def test_two_sessions_appending_same_pending_id_leave_one_row(file_dl):
    """Two independent DataLayer instances sharing a file store queue one row.

    The UNIQUE constraint on (queue, activity_id) ensures the second insert is
    rejected at the store level, regardless of whether either session checked
    for an existing row beforehand.
    """
    import vultron.adapters.driven.datalayer_sqlite as _mod

    # Open a second DataLayer pointing at the same on-disk database.
    actor_id = file_dl._actor_id
    db_url = file_dl._db_url
    second_dl = _mod.SqliteDataLayer(db_url, actor_id=actor_id)
    try:
        first_queued = file_dl.outbox_append("urn:test:shared-id")
        second_queued = second_dl.outbox_append("urn:test:shared-id")

        assert first_queued is True
        assert second_queued is False
        assert file_dl.outbox_list() == ["urn:test:shared-id"]
    finally:
        second_dl.clear_all()
        second_dl.close()


# ---------------------------------------------------------------------------
# File-backed integration test
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_file_backed_store_and_retrieve(file_dl):
    """Data written to a file-backed DataLayer is readable from the same URL."""
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(content="Integration test note")
    file_dl.save(note)
    result = file_dl.read(note.id_)
    assert result is not None
    assert result.id_ == note.id_  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# enqueue_callback — outbox_append (AC-1)
#
# There is no ``record_outbox_item`` counterpart.  Its distinguishing behaviour
# was firing the callback for an actor *other* than the DataLayer's own, which
# ADR-0073 removes: the queue is in the owning actor's store, so the only actor
# an append can notify is that store's.  Two tests that had been mechanically
# rewritten to call ``outbox_append`` were left here asserting the old explicit
# actor, and once corrected were exact duplicates of the two above.
# ---------------------------------------------------------------------------


def test_outbox_append_calls_callback_with_actor_id(scoped_dl):
    """outbox_append fires the enqueue_callback with the actor_id."""
    calls: list[str] = []
    scoped_dl.set_enqueue_callback(calls.append)
    scoped_dl.outbox_append("urn:test:act-001")
    assert calls == ["https://example.org/alice"]


@pytest.mark.spec("OX-06-002")
def test_outbox_append_does_not_call_back_for_an_id_already_pending(
    scoped_dl,
):
    """Nothing was queued, so there is nothing new for the drain to wake on."""
    calls: list[str] = []
    scoped_dl.set_enqueue_callback(calls.append)
    scoped_dl.outbox_append("urn:test:act-001")
    scoped_dl.outbox_append("urn:test:act-001")
    assert calls == ["https://example.org/alice"]


def test_outbox_append_no_callback_by_default():
    """outbox_append does not raise when no callback is set (default)."""
    dl = SqliteDataLayer(
        "sqlite:///:memory:", actor_id="https://example.org/bob"
    )
    dl.outbox_append("urn:test:act-001")  # should not raise
    dl.clear_all()
    dl.close()


def test_outbox_append_callback_cleared_by_set_none(scoped_dl):
    """set_enqueue_callback(None) disables future notifications."""
    calls: list[str] = []
    scoped_dl.set_enqueue_callback(calls.append)
    scoped_dl.set_enqueue_callback(None)
    scoped_dl.outbox_append("urn:test:act-001")
    assert calls == []


def test_clone_for_actor_inherits_callback():
    """clone_for_actor() inherits the parent's enqueue_callback."""
    calls: list[str] = []
    parent = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )
    parent.set_enqueue_callback(calls.append)
    clone = parent.clone_for_actor("https://example.org/alice")
    clone.outbox_append("urn:test:act-003")
    assert calls == ["https://example.org/alice"]
    parent.clear_all()
    parent.close()


def test_enqueue_callback_exception_does_not_propagate(scoped_dl):
    """A callback that raises must not abort the outbox_append operation."""

    def bad_callback(actor_id: str) -> None:
        raise RuntimeError("callback failure")

    scoped_dl.set_enqueue_callback(bad_callback)
    scoped_dl.outbox_append("urn:test:act-001")
    assert "urn:test:act-001" in scoped_dl.outbox_list()


def test_set_enqueue_callback_replaces_previous(scoped_dl):
    """set_enqueue_callback replaces any previously registered callback."""
    calls_a: list[str] = []
    calls_b: list[str] = []
    scoped_dl.set_enqueue_callback(calls_a.append)
    scoped_dl.set_enqueue_callback(calls_b.append)
    scoped_dl.outbox_append("urn:test:act-001")
    assert calls_a == []
    assert calls_b == ["https://example.org/alice"]
