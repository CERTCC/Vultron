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
"""No sender-sequence hold timer outlives what started it (#6148).

The timer reads every hosted actor's store, on its app's event loop and in
the worker thread each round is offloaded to (SYNC-21-011); per-test store
disposal closing a connection under that read segfaults the worker.  These
pin that the production lifespan's shutdown stops the timer, and that the
root conftest's disposal stops a leaked timer before it closes any store,
then fails the leaking test by name.
"""

import asyncio
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from test.support.hold_timers import (
    HoldTimerLeakedError,
    stop_hold_timer_from_another_thread,
)
from vultron.adapters.driven import datalayer_sqlite
from vultron.adapters.driving.fastapi import sender_sequence_holds as holds

_WAIT_SECONDS = 5.0


@pytest.fixture
def no_hosted_actors(monkeypatch):
    """A timer round, if one ran, would read no store."""
    monkeypatch.setattr(holds.actor_hosts, "hosted_actor_ids", lambda: [])


@pytest.fixture
def disposals(monkeypatch) -> list[str]:
    """Record the store disposals instead of performing them."""
    calls: list[str] = []
    monkeypatch.setattr(
        datalayer_sqlite, "reset_datalayer", lambda: calls.append("stores")
    )
    monkeypatch.setattr(
        datalayer_sqlite,
        "reset_store_claimants",
        lambda: calls.append("claimants"),
    )
    return calls


@pytest.fixture
def root_disposal(request) -> object:
    """The root conftest's registered ``_dispose_actor_stores_between_tests``.

    Driven through the fixture pytest actually runs, so a test fails if the
    conftest stops routing disposal through the guard.
    """
    name = "_dispose_actor_stores_between_tests"
    (fixture_def,) = request._fixturemanager.getfixturedefs(name, request.node)
    return fixture_def.func


def _run_teardown(fixture_func) -> None:
    """Run a yield fixture's teardown, as pytest does after a test."""
    steps = fixture_func()
    next(steps)
    with pytest.raises(StopIteration):
        next(steps)


@contextmanager
def _timer_on_a_loop_thread() -> Iterator[holds.SenderSequenceHoldTimer]:
    """A hold timer running on an event loop in another thread, as a
    TestClient's portal runs one."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()

    async def _start() -> holds.SenderSequenceHoldTimer:
        return holds.start_sender_sequence_hold_timer(None)

    timer = asyncio.run_coroutine_threadsafe(_start(), loop).result(
        _WAIT_SECONDS
    )
    try:
        yield timer
    finally:
        if not timer.task.done():
            asyncio.run_coroutine_threadsafe(
                holds.finish_sender_sequence_hold_timer(timer), loop
            ).result(_WAIT_SECONDS)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(_WAIT_SECONDS)
        loop.close()


def test_a_started_timer_runs_until_it_is_finished(no_hosted_actors):
    async def _body() -> tuple[bool, bool]:
        timer = holds.start_sender_sequence_hold_timer(None)
        while_running = timer in holds.running_sender_sequence_hold_timers()
        await holds.finish_sender_sequence_hold_timer(timer)
        after = timer in holds.running_sender_sequence_hold_timers()
        return while_running, after

    while_running, after = asyncio.run(_body())

    assert while_running
    assert not after


def test_disposal_stops_a_leaked_timer_then_disposes_then_fails_by_name(
    no_hosted_actors, disposals, root_disposal
):
    with _timer_on_a_loop_thread() as timer:
        with pytest.raises(HoldTimerLeakedError, match="hold timer"):
            _run_teardown(root_disposal)

        assert timer.stop.is_set()
        assert timer.task.done() and not timer.task.cancelled()
    assert disposals == ["stores", "claimants"]


def test_disposal_with_no_timer_running_disposes_and_passes(
    disposals, root_disposal
):
    _run_teardown(root_disposal)

    assert disposals == ["stores", "claimants"]


def test_a_timer_whose_loop_stopped_leaves_the_stores_open(
    no_hosted_actors, disposals, root_disposal
):
    loop = asyncio.new_event_loop()

    async def _start() -> holds.SenderSequenceHoldTimer:
        return holds.start_sender_sequence_hold_timer(None)

    timer = loop.run_until_complete(_start())
    try:
        with pytest.raises(HoldTimerLeakedError, match=r"not\s+disposed"):
            _run_teardown(root_disposal)
        assert disposals == []
    finally:
        loop.run_until_complete(holds.finish_sender_sequence_hold_timer(timer))
        loop.close()


def test_stopping_a_timer_from_its_own_loop_is_refused(no_hosted_actors):
    async def _body() -> None:
        timer = holds.start_sender_sequence_hold_timer(None)
        try:
            with pytest.raises(RuntimeError, match="own loop"):
                stop_hold_timer_from_another_thread(timer)
        finally:
            await holds.finish_sender_sequence_hold_timer(timer)

    asyncio.run(_body())


@pytest.mark.spec("SYNC-21-011")
def test_the_production_lifespan_stops_its_hold_timer_at_shutdown(
    no_hosted_actors,
):
    from vultron.adapters.driving.fastapi.app import app_v2

    with TestClient(app_v2):
        timer = app_v2.state.sender_sequence_hold_timer
        assert timer in holds.running_sender_sequence_hold_timers()

    assert holds.running_sender_sequence_hold_timers() == []
    # Closing the portal's loop would cancel a timer the shutdown forgot and
    # empty the registry anyway; only a signalled stop ends it uncancelled.
    assert timer.stop.is_set()
    assert timer.task.done() and not timer.task.cancelled()
