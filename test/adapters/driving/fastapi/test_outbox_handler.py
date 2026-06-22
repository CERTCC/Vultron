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
Unit tests for the outbox_handler FIFO processing loop.

Tests ``outbox_handler`` — the loop that drains an actor's outbox and
dispatches each item via ``handle_outbox_item``.

Module under test: ``vultron/adapters/driving/fastapi/outbox_handler.py``

Spec coverage:
- OX-01-001: Actor MUST have an outbox collection.
- OX-01-002: Outbox MUST preserve insertion order (FIFO).
- OX-03-001: Activities in outbox MUST be delivered to recipient inboxes.
- OX-03-002/003: Delivery occurs after handler; MUST NOT block HTTP response.
"""

import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

from vultron.adapters.driving.fastapi import outbox_handler as oh

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_queue(*ids: str) -> list[str]:
    """Return a mutable list of activity ID strings."""
    return list(ids)


def _mock_dl_with_queue(
    queue: list[str], actor: SimpleNamespace | None = SimpleNamespace()
) -> MagicMock:
    """Return a MagicMock DataLayer backed by ``queue`` for outbox ops."""
    mock_dl = MagicMock()
    mock_dl.read.return_value = actor
    mock_dl.find_actor_by_short_id.return_value = actor
    mock_dl.outbox_list.side_effect = lambda: list(queue)
    mock_dl.outbox_pop.side_effect = lambda: queue.pop(0) if queue else None
    mock_dl.outbox_append.side_effect = lambda x: queue.append(x)
    return mock_dl


# ---------------------------------------------------------------------------
# outbox_handler — happy paths
# ---------------------------------------------------------------------------


def test_outbox_handler_processes_all_items(monkeypatch):
    """outbox_handler drains the actor's outbox entirely on success."""
    ids = [f"urn:test:item-{i}" for i in range(3)]
    queue = _make_queue(*ids)
    mock_dl = _mock_dl_with_queue(queue)

    processed = []

    async def fake_handle(actor_id, activity_id, dl, emitter):
        processed.append(activity_id)

    monkeypatch.setattr(oh, "handle_outbox_item", fake_handle)

    asyncio.run(oh.outbox_handler("actor-xyz", mock_dl))

    assert queue == []
    assert processed == ids


def test_outbox_handler_preserves_fifo_order(monkeypatch):
    """outbox_handler processes items in FIFO order (OX-01-002)."""
    ids = [f"urn:test:item-{i}" for i in range(4)]
    queue = _make_queue(*ids)
    mock_dl = _mock_dl_with_queue(queue)

    processed = []

    async def fake_handle(actor_id, activity_id, dl, emitter):
        processed.append(activity_id)

    monkeypatch.setattr(oh, "handle_outbox_item", fake_handle)

    asyncio.run(oh.outbox_handler("actor-xyz", mock_dl))

    assert processed == ids


def test_outbox_handler_empty_outbox_does_nothing(monkeypatch):
    """outbox_handler with empty outbox processes no items."""
    queue: list[str] = []
    mock_dl = _mock_dl_with_queue(queue)

    processed = []

    async def fake_handle(actor_id, activity_id, dl, emitter):
        processed.append(activity_id)

    monkeypatch.setattr(oh, "handle_outbox_item", fake_handle)

    asyncio.run(oh.outbox_handler("actor-xyz", mock_dl))

    assert processed == []


# ---------------------------------------------------------------------------
# outbox_handler — error handling
# ---------------------------------------------------------------------------


def test_outbox_handler_retries_and_aborts_after_too_many_errors(monkeypatch):
    """outbox_handler puts item back on error and aborts after > 3 errors."""
    queue = _make_queue("urn:test:bad-item")
    mock_dl = _mock_dl_with_queue(queue)

    async def always_raise(actor_id, activity_id, dl, emitter):
        raise RuntimeError("delivery failed")

    monkeypatch.setattr(oh, "handle_outbox_item", always_raise)

    asyncio.run(oh.outbox_handler("actor-xyz", mock_dl))

    # item should be back in the queue after the retry limit is hit
    assert "urn:test:bad-item" in queue


def test_outbox_handler_returns_early_when_actor_not_found(
    monkeypatch, caplog
):
    """outbox_handler must return early (not raise) when actor is None."""
    queue: list[str] = []
    mock_dl = _mock_dl_with_queue(
        queue, actor=cast(SimpleNamespace | None, None)
    )
    mock_dl.read.return_value = None
    mock_dl.find_actor_by_short_id.return_value = None

    with caplog.at_level("WARNING"):
        asyncio.run(oh.outbox_handler("missing-actor", mock_dl))

    assert "missing-actor" in caplog.text


def test_outbox_handler_continues_after_one_error(monkeypatch):
    """outbox_handler continues processing subsequent items after a single error."""
    queue = _make_queue("urn:test:bad", "urn:test:good")
    mock_dl = _mock_dl_with_queue(queue)

    call_count = [0]
    processed = []

    async def sometimes_raise(actor_id, activity_id, dl, emitter):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("first item fails once")
        processed.append(activity_id)

    monkeypatch.setattr(oh, "handle_outbox_item", sometimes_raise)

    asyncio.run(oh.outbox_handler("actor-xyz", mock_dl))

    assert "urn:test:good" in processed


def test_outbox_handler_resolves_actor_by_short_id(monkeypatch):
    """outbox_handler falls back to find_actor_by_short_id when full ID lookup fails."""
    queue: list[str] = []
    mock_dl = _mock_dl_with_queue(queue)
    mock_dl.read.return_value = None  # full-ID lookup fails
    mock_dl.find_actor_by_short_id.return_value = SimpleNamespace(
        id_="https://example.org/actors/bob"
    )

    asyncio.run(oh.outbox_handler("bob", mock_dl))

    mock_dl.find_actor_by_short_id.assert_called_once_with("bob")
