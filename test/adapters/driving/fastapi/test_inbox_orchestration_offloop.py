"""The inbox BT pipeline must not run on the ASGI event loop (IE-06-002, BT-11-002).

``run_inbox_pipeline`` is an ``async def`` background task, so Starlette runs
it on the event loop.  ``process_payload`` is synchronous — it ticks the inbox
BT, takes the BT global lock, and does SQLite I/O.  Calling it directly from the
coroutine stalls the whole container for the duration of every inbound
activity: no HTTP response can be sent, no delivery from a peer can be
accepted, and the co-hosted ``OutboxMonitor`` coroutine cannot drain.  The
fv/fcvcv demo flakes (#3033, #2898) were the CaseActor's outbox waiting on the
vendor's inbound BT ticks, one activity at a time.

These tests pin the remedy: the synchronous work runs in a worker thread, and
the loop keeps making progress while it runs.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from vultron.adapters.driving.fastapi.inbox_orchestration import (
    run_inbox_pipeline,
)
from vultron.core.behaviors.inbox import InboxOutcome, InboxOutcomeStatus

_ACTOR_ID = "https://example.org/actors/offloop"


@pytest.fixture(autouse=True)
def clear_actor_locks():
    from vultron.adapters.driving.fastapi import inbox_orchestration

    inbox_orchestration._actor_inbox_locks.clear()
    yield
    inbox_orchestration._actor_inbox_locks.clear()


@pytest.fixture
def quiet_pipeline(monkeypatch):
    """Stub the pipeline's collaborators so only threading is under test."""
    monkeypatch.setattr(
        "vultron.adapters.driving.fastapi.outbox_handler.outbox_handler",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "vultron.adapters.driving.fastapi.inbox_port_factories"
        "._resolve_actor_config",
        lambda: None,
    )
    dl = MagicMock()
    dl.inbox_list.return_value = []
    return dl


def _install_process_payload(monkeypatch, fn) -> None:
    # run_inbox_pipeline imports the symbol from the package at call time.
    monkeypatch.setattr("vultron.core.behaviors.inbox.process_payload", fn)


@pytest.mark.spec("IE-06-003")
@pytest.mark.spec("IE-06-002")
def test_process_payload_runs_off_the_event_loop(monkeypatch, quiet_pipeline):
    """The BT pipeline executes on a worker thread, not the loop thread."""
    seen: dict[str, Any] = {}

    def fake_process_payload(*args: Any, **kwargs: Any) -> InboxOutcome:
        seen["thread"] = threading.get_ident()
        return InboxOutcome(status=InboxOutcomeStatus.PROCESSED)

    _install_process_payload(monkeypatch, fake_process_payload)

    async def _run() -> int:
        await run_inbox_pipeline({}, quiet_pipeline, _ACTOR_ID, None, None)
        return threading.get_ident()

    loop_thread = asyncio.run(_run())

    assert "thread" in seen, "process_payload was never called"
    assert seen["thread"] != loop_thread, (
        "process_payload ran on the event-loop thread; every inbound BT tick"
        " stalls the container's HTTP service and outbox drain (IE-06-002,"
        " BT-11-002)"
    )


@pytest.mark.spec("IE-06-003")
@pytest.mark.spec("BT-11-002")
def test_event_loop_keeps_serving_while_a_payload_is_processed(
    monkeypatch, quiet_pipeline
):
    """A concurrent coroutine progresses while process_payload blocks.

    A 0.3 s synchronous block on the loop would let the ticker run at most
    once (before the block) — the assertion of several ticks leaves a wide
    margin either way, so this is not a timing-sensitive test.
    """

    def blocking_process_payload(*args: Any, **kwargs: Any) -> InboxOutcome:
        time.sleep(0.3)
        return InboxOutcome(status=InboxOutcomeStatus.PROCESSED)

    _install_process_payload(monkeypatch, blocking_process_payload)

    async def _run() -> int:
        done = asyncio.Event()
        ticks = 0

        async def _pipeline() -> None:
            try:
                await run_inbox_pipeline(
                    {}, quiet_pipeline, _ACTOR_ID, None, None
                )
            finally:
                done.set()

        async def _ticker() -> None:
            nonlocal ticks
            while not done.is_set():
                ticks += 1
                await asyncio.sleep(0.01)

        await asyncio.gather(_pipeline(), _ticker())
        return ticks

    ticks = asyncio.run(_run())
    assert ticks >= 5, (
        f"the event loop advanced only {ticks} time(s) during a 0.3 s"
        " process_payload — the inbox pipeline is blocking the loop"
    )
