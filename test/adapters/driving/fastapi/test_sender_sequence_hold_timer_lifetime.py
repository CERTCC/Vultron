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

The timer reads every hosted actor's store from its app's event-loop thread
(SYNC-21-011); per-test store disposal closing a connection under that read
segfaults the worker.  These pin that the production lifespan's shutdown
leaves no timer running, and that disposal refuses, by name, while one runs.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from test.support.hold_timers import (
    HoldTimerLeakedError,
    refuse_disposal_under_live_hold_timer,
)
from vultron.adapters.driving.fastapi import sender_sequence_holds as holds


@pytest.fixture
def no_hosted_actors(monkeypatch):
    """A timer round, if one ran, would read no store."""
    monkeypatch.setattr(holds.actor_hosts, "hosted_actor_ids", lambda: [])


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


def test_store_disposal_is_refused_by_name_while_a_hold_timer_runs(
    no_hosted_actors,
):
    async def _body() -> None:
        timer = holds.start_sender_sequence_hold_timer(None)
        try:
            with pytest.raises(HoldTimerLeakedError, match="hold timer"):
                refuse_disposal_under_live_hold_timer()
        finally:
            await holds.finish_sender_sequence_hold_timer(timer)
        refuse_disposal_under_live_hold_timer()

    asyncio.run(_body())


@pytest.mark.spec("SYNC-21-011")
def test_the_production_lifespan_leaves_no_hold_timer_running(
    no_hosted_actors,
):
    from vultron.adapters.driving.fastapi.app import app_v2

    with TestClient(app_v2):
        timer = app_v2.state.sender_sequence_hold_timer
        assert timer in holds.running_sender_sequence_hold_timers()

    assert holds.running_sender_sequence_hold_timers() == []
