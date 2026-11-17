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
"""The demo ``client`` fixture leaves no lifespan background work running.

The fixture is module-scoped, so the app it starts outlives every test in
the module, and the root conftest disposes the actor stores after each one.
Background work left running (the hold timer, the outbox monitor, the
startup replay or position statements) reads those stores, on the app's
loop and in worker threads, while they are closed, which segfaults the
worker (#6148).

The same tests check that a test using the fixture runs inside the
store-sharing guard (#6085).
"""

import asyncio

from fastapi.testclient import TestClient

from test.support import store_sharing
from vultron.adapters.driven.datalayer_sqlite import engine as sqlite_engine
from vultron.adapters.driving.fastapi.sender_sequence_holds import (
    running_sender_sequence_hold_timers,
)

#: The coroutines the production lifespan starts as background tasks.
_LIFESPAN_BACKGROUND_WORK = {
    "OutboxMonitor._run_loop",
    "_end_holds_on_interval",
    "replay_hosted_inbox_queues",
    "_state_positions_then_repeat",
}


async def _running_task_coroutines() -> set[str]:
    current = asyncio.current_task()
    return {
        # A Task's coroutine is typed as the Coroutine ABC, which declares
        # no ``__qualname__``; every coroutine object has one.
        getattr(task.get_coro(), "__qualname__", repr(task))
        for task in asyncio.all_tasks()
        if task is not current and not task.done()
    }


def test_the_demo_client_has_stopped_the_hold_timer_before_any_test(
    client: TestClient,
):
    assert running_sender_sequence_hold_timers() == []


def test_the_demo_client_has_ended_all_lifespan_background_work(
    client: TestClient,
):
    portal = client.portal
    assert portal is not None

    running = portal.call(_running_task_coroutines)

    assert not running & _LIFESPAN_BACKGROUND_WORK


def test_a_demo_client_test_runs_inside_the_store_sharing_guard(
    client: TestClient,
):
    """Both the fixture's guard and the per-test autouse guard are attached."""
    guards = [
        handler
        for handler in sqlite_engine.logger.handlers
        if isinstance(handler, store_sharing._SharedStoreRecords)
    ]

    assert len(guards) == 2
