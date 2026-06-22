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
integration, set_enqueue_callback, record_outbox_item, and clone_for_actor.
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
# enqueue_callback — outbox_append and record_outbox_item (AC-1)
# ---------------------------------------------------------------------------


def test_outbox_append_calls_callback_with_actor_id(scoped_dl):
    """outbox_append fires the enqueue_callback with the actor_id."""
    calls: list[str] = []
    scoped_dl.set_enqueue_callback(calls.append)
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


def test_record_outbox_item_calls_callback_with_actor_id():
    """record_outbox_item fires the enqueue_callback with the explicit actor_id."""
    dl = SqliteDataLayer("sqlite:///:memory:")
    calls: list[str] = []
    dl.set_enqueue_callback(calls.append)
    dl.record_outbox_item("https://example.org/carol", "urn:test:act-002")
    assert calls == ["https://example.org/carol"]
    dl.clear_all()
    dl.close()


def test_record_outbox_item_no_callback_by_default():
    """record_outbox_item does not raise when no callback is set."""
    dl = SqliteDataLayer("sqlite:///:memory:")
    dl.record_outbox_item("https://example.org/carol", "urn:test:act-002")
    dl.clear_all()
    dl.close()


def test_clone_for_actor_inherits_callback():
    """clone_for_actor() inherits the parent's enqueue_callback."""
    calls: list[str] = []
    parent = SqliteDataLayer("sqlite:///:memory:")
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
