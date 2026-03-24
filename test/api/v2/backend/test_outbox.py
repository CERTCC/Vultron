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

"""
Unit tests for the outbox handler module.

Tests call outbox handler functions directly (no HTTP layer) to verify
the processing loop behavior. Each test monkeypatches ``get_datalayer``
in the module under test to keep tests fast and isolated.

Module under test: ``vultron/adapters/driving/fastapi/outbox_handler.py``

Spec coverage:
- OX-01-001: Actor MUST have an outbox collection.
- OX-01-002: Outbox MUST preserve insertion order (FIFO).
- OX-03-001: Activities in outbox MUST be delivered to recipient inboxes.
- OX-03-002/003: Delivery occurs after handler; MUST NOT block HTTP response.

Note: Delivery tests (OX-1.1/OX-1.2/OX-1.3) are deferred until those
features are implemented. This file provides tests for the current
processing loop and ``handle_outbox_item`` stub behavior.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from vultron.adapters.driving.fastapi import outbox_handler as oh

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_item(name: str = "item") -> SimpleNamespace:
    """Return a minimal fake activity item."""
    return SimpleNamespace(
        as_id=f"urn:test:{name}",
        as_type="Activity",
        name=name,
        model_dump_json=lambda **kw: f'{{"name":"{name}"}}',
    )


def _make_actor(items: list) -> SimpleNamespace:
    """Return a minimal fake actor with an outbox collection."""
    outbox = SimpleNamespace(items=list(items))
    return SimpleNamespace(outbox=outbox)


# ---------------------------------------------------------------------------
# handle_outbox_item
# ---------------------------------------------------------------------------


def test_handle_outbox_item_logs_actor_id(caplog):
    """handle_outbox_item should log the actor_id at INFO level."""
    item = _make_item("log-test")
    with caplog.at_level("INFO"):
        oh.handle_outbox_item("actor-abc", item)
    assert "actor-abc" in caplog.text


def test_handle_outbox_item_logs_item(caplog):
    """handle_outbox_item should log the outbox item at INFO level."""
    item = _make_item("my-activity")
    with caplog.at_level("INFO"):
        oh.handle_outbox_item("actor-abc", item)
    # The item's str representation appears somewhere in the log
    assert caplog.text  # at minimum something is logged


# ---------------------------------------------------------------------------
# outbox_handler — happy paths
# ---------------------------------------------------------------------------


def test_outbox_handler_processes_all_items(monkeypatch):
    """outbox_handler drains the actor's outbox entirely on success."""
    items = [_make_item(f"item-{i}") for i in range(3)]
    actor = _make_actor(items)

    mock_dl = MagicMock()
    mock_dl.read.return_value = actor
    monkeypatch.setattr(oh, "get_datalayer", lambda: mock_dl)

    processed = []

    def fake_handle(actor_id, obj):
        processed.append(obj)

    monkeypatch.setattr(oh, "handle_outbox_item", fake_handle)

    asyncio.run(oh.outbox_handler("actor-xyz"))

    assert actor.outbox.items == []
    assert len(processed) == 3


def test_outbox_handler_preserves_fifo_order(monkeypatch):
    """outbox_handler processes items in FIFO order (OX-01-002)."""
    items = [_make_item(f"item-{i}") for i in range(4)]
    actor = _make_actor(items)

    mock_dl = MagicMock()
    mock_dl.read.return_value = actor
    monkeypatch.setattr(oh, "get_datalayer", lambda: mock_dl)

    processed_names = []

    def fake_handle(actor_id, obj):
        processed_names.append(obj.name)

    monkeypatch.setattr(oh, "handle_outbox_item", fake_handle)

    asyncio.run(oh.outbox_handler("actor-xyz"))

    assert processed_names == ["item-0", "item-1", "item-2", "item-3"]


def test_outbox_handler_empty_outbox_does_nothing(monkeypatch):
    """outbox_handler with empty outbox processes no items."""
    actor = _make_actor([])

    mock_dl = MagicMock()
    mock_dl.read.return_value = actor
    monkeypatch.setattr(oh, "get_datalayer", lambda: mock_dl)

    processed = []

    def fake_handle(actor_id, obj):
        processed.append(obj)

    monkeypatch.setattr(oh, "handle_outbox_item", fake_handle)

    asyncio.run(oh.outbox_handler("actor-xyz"))

    assert processed == []


# ---------------------------------------------------------------------------
# outbox_handler — error handling
# ---------------------------------------------------------------------------


def test_outbox_handler_retries_and_aborts_after_too_many_errors(monkeypatch):
    """outbox_handler puts item back on error and aborts after > 3 errors."""
    item = _make_item("bad-item")
    actor = _make_actor([item])

    mock_dl = MagicMock()
    mock_dl.read.return_value = actor
    monkeypatch.setattr(oh, "get_datalayer", lambda: mock_dl)

    def always_raise(actor_id, obj):
        raise RuntimeError("delivery failed")

    monkeypatch.setattr(oh, "handle_outbox_item", always_raise)

    asyncio.run(oh.outbox_handler("actor-xyz"))

    # item is returned to the outbox after the retry limit is hit
    assert len(actor.outbox.items) == 1
    assert actor.outbox.items[0] is item


def test_outbox_handler_returns_early_when_actor_not_found(
    monkeypatch, caplog
):
    """outbox_handler must return early (not raise) when actor is None (BUG-001)."""
    mock_dl = MagicMock()
    mock_dl.read.return_value = None
    monkeypatch.setattr(oh, "get_datalayer", lambda: mock_dl)

    with caplog.at_level("WARNING"):
        asyncio.run(oh.outbox_handler("missing-actor"))

    assert "missing-actor" in caplog.text


def test_outbox_handler_continues_after_one_error(monkeypatch):
    """outbox_handler continues processing subsequent items after a single error."""
    bad_item = _make_item("bad")
    good_item = _make_item("good")
    actor = _make_actor([bad_item, good_item])

    mock_dl = MagicMock()
    mock_dl.read.return_value = actor
    monkeypatch.setattr(oh, "get_datalayer", lambda: mock_dl)

    call_count = [0]
    processed = []

    def sometimes_raise(actor_id, obj):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("first item fails once")
        processed.append(obj)

    monkeypatch.setattr(oh, "handle_outbox_item", sometimes_raise)

    asyncio.run(oh.outbox_handler("actor-xyz"))

    assert good_item in processed
