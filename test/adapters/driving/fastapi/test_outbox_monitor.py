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

"""Unit tests for OutboxMonitor (OUTBOX-MON-1).

Tests cover drain_all(), error handling, and start()/stop() lifecycle.
The asyncio task loop is not exercised directly; only drain_all() and the
start/stop lifecycle are tested to keep tests deterministic.

Module under test: ``vultron/adapters/driving/fastapi/outbox_monitor.py``
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vultron.adapters.driving.fastapi.outbox_monitor import OutboxMonitor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_dl(has_items: bool = False) -> MagicMock:
    """Return a MagicMock DataLayer with a configurable outbox state."""
    dl = MagicMock()
    dl.outbox_list.return_value = ["urn:test:act-001"] if has_items else []
    return dl


def _make_monitor(
    actor_dls: dict | None = None,
    shared_dl: MagicMock | None = None,
    emitter: AsyncMock | None = None,
) -> OutboxMonitor:
    """Build an OutboxMonitor with injected test doubles."""
    factory = (lambda: actor_dls) if actor_dls is not None else (lambda: {})
    return OutboxMonitor(
        poll_interval=0.01,
        actor_datalayers_factory=factory,
        shared_dl=shared_dl or MagicMock(),
        emitter=emitter,
    )


# ---------------------------------------------------------------------------
# drain_all — happy paths
# ---------------------------------------------------------------------------


def test_drain_all_skips_empty_outbox():
    """drain_all does nothing when all actor outboxes are empty."""
    dl = _mock_dl(has_items=False)
    monitor = _make_monitor(actor_dls={"alice": dl})

    with patch(
        "vultron.adapters.driving.fastapi.outbox_monitor.outbox_handler",
        new_callable=AsyncMock,
    ) as mock_handler:
        asyncio.run(monitor.drain_all())

    mock_handler.assert_not_called()


def test_drain_all_calls_outbox_handler_for_actor_with_items():
    """drain_all calls outbox_handler for actors whose outbox is non-empty."""
    dl = _mock_dl(has_items=True)
    shared = MagicMock()
    monitor = _make_monitor(actor_dls={"alice": dl}, shared_dl=shared)

    with patch(
        "vultron.adapters.driving.fastapi.outbox_monitor.outbox_handler",
        new_callable=AsyncMock,
    ) as mock_handler:
        asyncio.run(monitor.drain_all())

    mock_handler.assert_called_once_with(
        "alice", dl, shared_dl=shared, emitter=None
    )


def test_drain_all_skips_empty_and_processes_non_empty():
    """drain_all processes only actors with pending items."""
    alice_dl = _mock_dl(has_items=False)
    bob_dl = _mock_dl(has_items=True)
    shared = MagicMock()
    monitor = _make_monitor(
        actor_dls={"alice": alice_dl, "bob": bob_dl}, shared_dl=shared
    )

    with patch(
        "vultron.adapters.driving.fastapi.outbox_monitor.outbox_handler",
        new_callable=AsyncMock,
    ) as mock_handler:
        asyncio.run(monitor.drain_all())

    mock_handler.assert_called_once_with(
        "bob", bob_dl, shared_dl=shared, emitter=None
    )


def test_drain_all_calls_handler_for_multiple_actors():
    """drain_all calls outbox_handler once per actor that has pending items."""
    dls = {f"actor-{i}": _mock_dl(has_items=True) for i in range(3)}
    shared = MagicMock()
    monitor = _make_monitor(actor_dls=dls, shared_dl=shared)

    with patch(
        "vultron.adapters.driving.fastapi.outbox_monitor.outbox_handler",
        new_callable=AsyncMock,
    ) as mock_handler:
        asyncio.run(monitor.drain_all())

    assert mock_handler.call_count == 3


# ---------------------------------------------------------------------------
# drain_all — error handling
# ---------------------------------------------------------------------------


def test_drain_all_continues_after_error_for_one_actor(caplog):
    """drain_all logs errors and continues processing remaining actors."""
    alice_dl = _mock_dl(has_items=True)
    bob_dl = _mock_dl(has_items=True)
    shared = MagicMock()
    monitor = _make_monitor(
        actor_dls={"alice": alice_dl, "bob": bob_dl}, shared_dl=shared
    )

    call_count = [0]

    async def sometimes_raises(actor_id, dl, shared_dl, emitter):
        call_count[0] += 1
        if actor_id == "alice":
            raise RuntimeError("delivery failed")

    with patch(
        "vultron.adapters.driving.fastapi.outbox_monitor.outbox_handler",
        new=sometimes_raises,
    ):
        with caplog.at_level("ERROR"):
            asyncio.run(monitor.drain_all())

    assert call_count[0] == 2
    assert "alice" in caplog.text


def test_drain_all_logs_error_on_exception(caplog):
    """drain_all logs at ERROR level when outbox_handler raises."""
    dl = _mock_dl(has_items=True)
    monitor = _make_monitor(actor_dls={"bad-actor": dl})

    async def always_raises(actor_id, dl, shared_dl, emitter):
        raise RuntimeError("boom")

    with patch(
        "vultron.adapters.driving.fastapi.outbox_monitor.outbox_handler",
        new=always_raises,
    ):
        with caplog.at_level("ERROR"):
            asyncio.run(monitor.drain_all())

    assert "bad-actor" in caplog.text
    assert "ERROR" in caplog.text


def test_drain_all_empty_actor_dict_does_nothing():
    """drain_all with no registered actors is a silent no-op."""
    monitor = _make_monitor(actor_dls={})

    with patch(
        "vultron.adapters.driving.fastapi.outbox_monitor.outbox_handler",
        new_callable=AsyncMock,
    ) as mock_handler:
        asyncio.run(monitor.drain_all())

    mock_handler.assert_not_called()


# ---------------------------------------------------------------------------
# start() / stop() lifecycle
# ---------------------------------------------------------------------------


def test_start_creates_asyncio_task():
    """start() creates an asyncio.Task that is accessible via _task."""

    async def _run():
        monitor = _make_monitor()
        monitor.start()
        assert monitor._task is not None
        assert not monitor._task.done()
        monitor.stop()
        # Allow the cancelled task to propagate
        await asyncio.sleep(0)

    asyncio.run(_run())


def test_stop_cancels_task():
    """stop() cancels the background task and sets _task to None."""

    async def _run():
        monitor = _make_monitor()
        monitor.start()
        task = monitor._task
        assert task is not None
        monitor.stop()
        assert monitor._task is None
        # Give the event loop a chance to process the cancellation
        await asyncio.sleep(0)
        assert task.cancelled() or task.done()

    asyncio.run(_run())


def test_start_twice_is_noop(caplog):
    """Calling start() a second time while running logs a warning and is safe."""

    async def _run():
        monitor = _make_monitor()
        monitor.start()
        first_task = monitor._task
        with caplog.at_level("WARNING"):
            monitor.start()  # second call
        assert monitor._task is first_task
        monitor.stop()
        await asyncio.sleep(0)

    asyncio.run(_run())
    assert "already running" in caplog.text


def test_stop_without_start_is_safe():
    """stop() before start() does not raise."""
    monitor = _make_monitor()
    monitor.stop()  # should not raise


def test_start_after_stop_creates_new_task():
    """start() can be called again after stop() to restart the monitor."""

    async def _run():
        monitor = _make_monitor()
        monitor.start()
        monitor.stop()
        await asyncio.sleep(0)
        monitor.start()
        assert monitor._task is not None
        assert not monitor._task.done()
        monitor.stop()
        await asyncio.sleep(0)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# drain_all — uses default shared_dl when none provided
# ---------------------------------------------------------------------------


def test_drain_all_uses_get_datalayer_as_default_shared_dl():
    """drain_all falls back to get_datalayer() when shared_dl is not set."""
    dl = _mock_dl(has_items=True)
    monitor = OutboxMonitor(
        poll_interval=0.01,
        actor_datalayers_factory=lambda: {"actor-x": dl},
        shared_dl=None,
    )
    fake_shared = MagicMock()

    with patch(
        "vultron.adapters.driving.fastapi.outbox_monitor.get_datalayer",
        return_value=fake_shared,
    ):
        with patch(
            "vultron.adapters.driving.fastapi.outbox_monitor.outbox_handler",
            new_callable=AsyncMock,
        ) as mock_handler:
            asyncio.run(monitor.drain_all())

    mock_handler.assert_called_once_with(
        "actor-x", dl, shared_dl=fake_shared, emitter=None
    )


# ---------------------------------------------------------------------------
# drain_all — get_all_actor_datalayers default factory
# ---------------------------------------------------------------------------


def test_drain_all_uses_get_all_actor_datalayers_by_default():
    """OutboxMonitor uses get_all_actor_datalayers() by default."""
    dl = _mock_dl(has_items=True)
    monitor = OutboxMonitor(
        poll_interval=0.01,
        actor_datalayers_factory=None,
        shared_dl=MagicMock(),
    )

    with patch(
        "vultron.adapters.driving.fastapi.outbox_monitor.get_all_actor_datalayers",
        return_value={"actor-y": dl},
    ):
        with patch(
            "vultron.adapters.driving.fastapi.outbox_monitor.outbox_handler",
            new_callable=AsyncMock,
        ) as mock_handler:
            asyncio.run(monitor.drain_all())

    mock_handler.assert_called_once()
    call_actor_id = mock_handler.call_args[0][0]
    assert call_actor_id == "actor-y"


# ---------------------------------------------------------------------------
# run_loop integration — logs started/stopped messages
# ---------------------------------------------------------------------------


def test_run_loop_logs_started_and_stopped(caplog):
    """OutboxMonitor logs start and stop messages during its run loop."""

    async def _run():
        monitor = _make_monitor()
        with caplog.at_level("INFO"):
            monitor.start()
            await asyncio.sleep(0.02)
            monitor.stop()
            await asyncio.sleep(0)

    asyncio.run(_run())
    assert "OutboxMonitor started" in caplog.text
    assert "OutboxMonitor stopped" in caplog.text


@pytest.mark.parametrize(
    "poll_interval",
    [0.1, 0.5, 1.0, 2.0],
)
def test_outbox_monitor_accepts_various_poll_intervals(poll_interval):
    """OutboxMonitor can be constructed with various poll intervals."""
    monitor = OutboxMonitor(poll_interval=poll_interval)
    assert monitor._poll_interval == poll_interval
