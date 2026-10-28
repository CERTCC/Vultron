"""The inbox BT pipeline must not run on the ASGI event loop (IE-06-002, BT-11-002).

``run_inbox_pipeline`` is an ``async def`` background task, so Starlette runs
it on the event loop.  ``process_payload`` is synchronous — it ticks the inbox
BT, takes the BT global lock, and does SQLite I/O.  Calling it directly from the
coroutine stalls the whole container for the duration of every inbound
activity: no HTTP response can be sent, no delivery from a peer can be
accepted, and the co-hosted ``OutboxMonitor`` coroutine cannot drain.  The
rv/rcvcv demo flakes (#3033, #2898) were the CaseActor's outbox waiting on the
vendor's inbound BT ticks, one activity at a time.

These tests pin the remedy: the synchronous work runs in a worker thread, and
the loop keeps making progress while it runs.
"""

from __future__ import annotations

import asyncio
import threading
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
        "vultron.adapters.driving.fastapi.inbox_orchestration.outbox_handler",
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
    # run_inbox_pipeline calls the name its module imported at load time.
    monkeypatch.setattr(
        "vultron.adapters.driving.fastapi.inbox_orchestration.process_payload",
        fn,
    )


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


#: How long a parked ``process_payload`` waits for the loop to release it.
#: It bounds only the failing case: when the loop is free the release comes
#: as soon as the loop runs a coroutine, however loaded the machine is.
_RELEASE_WAIT_SECONDS = 10.0


@pytest.mark.spec("IE-06-003")
@pytest.mark.spec("BT-11-002")
def test_event_loop_keeps_serving_while_a_payload_is_processed(
    monkeypatch, quiet_pipeline
):
    """The loop runs a coroutine while ``process_payload`` is parked.

    ``process_payload`` blocks until a coroutine on the loop releases it, so
    it can return released only if the loop kept running while it waited.
    Run on the loop thread, it would hold the loop until its wait timed out
    and return unreleased.  No count of loop ticks in a fixed window is
    involved: CPU contention can slow the release but cannot fake it (#4913).
    """
    parked = threading.Event()
    release = threading.Event()
    released: list[bool] = []

    def parked_process_payload(*args: Any, **kwargs: Any) -> InboxOutcome:
        parked.set()
        released.append(release.wait(timeout=_RELEASE_WAIT_SECONDS))
        return InboxOutcome(status=InboxOutcomeStatus.PROCESSED)

    _install_process_payload(monkeypatch, parked_process_payload)

    async def _run() -> bool:
        pipeline = asyncio.create_task(
            run_inbox_pipeline({}, quiet_pipeline, _ACTOR_ID, None, None)
        )
        while not parked.is_set() and not pipeline.done():
            await asyncio.sleep(0.001)
        if not parked.is_set():
            # The pipeline finished without reaching process_payload: surface
            # its own exception rather than spin until the test timeout.
            await pipeline
            pytest.fail("run_inbox_pipeline never called process_payload")
        # The loop is running this coroutine while process_payload waits.
        served_while_parked = not pipeline.done()
        release.set()
        await pipeline
        return served_while_parked

    served_while_parked = asyncio.run(_run())

    assert released == [True], (
        "process_payload was never released: the loop could not run while"
        " it was processed, so the inbox pipeline is blocking the loop"
        " (IE-06-002, BT-11-002)"
    )
    assert served_while_parked
