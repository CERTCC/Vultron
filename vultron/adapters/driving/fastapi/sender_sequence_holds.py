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

"""End each sender-sequence hold once its wait has passed (SYNC-21-011).

The CASE_MANAGER holds a participant's activity that arrives past a gap in
the sender's ``senderSequence`` (SYNC-21-010).  The hold must end once its
wait has passed, whether or not anything else arrives, so a lost activity
delays its sender's later ones by at most the wait (ADR-0178).  An arrival
from the same sender ends an expired hold too, but a sender that sends
nothing more needs this timer.

The app lifespan starts :func:`start_sender_sequence_hold_timer` once.  Every
quarter of ``ledger.sender_sequence_hold_seconds`` it ends, in every hosted
actor's store, each hold whose oldest activity has waited the wait
(:func:`end_expired_holds`), and replays the held activities that makes due,
in number order, under the actor's inbox lock
(:func:`~vultron.adapters.driving.fastapi.inbox_orchestration.run_actor_work_then_replay`).
A hold therefore ends at most a quarter of its wait late.
"""

import asyncio
import logging
from dataclasses import dataclass
from functools import partial
from typing import cast

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driven.clock import SystemClock
from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driving.fastapi.inbox_handler import (
    queue_due_held_activities,
)
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    run_actor_work_then_replay,
)
from vultron.config.app import get_config
from vultron.core.behaviors.bridge.act_instant import open_act
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.clock import ClockPort
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.emitter import ActivityEmitter
from vultron.core.services.sender_sequence_order import (
    end_expired_sender_sequence_holds,
)

logger = logging.getLogger(__name__)


def _end_expired_holds_into(
    actor_dl: DataLayer, clock: ClockPort, ended: list[int]
) -> None:
    """:func:`end_expired_holds`, appending its count to *ended*."""
    ended.append(end_expired_holds(actor_dl, clock))


def end_expired_holds(actor_dl: DataLayer, clock: ClockPort) -> int:
    """End the holds in *actor_dl* whose wait has passed; queue what is due.

    The wait is ``ledger.sender_sequence_hold_seconds`` (SYNC-21-021).  Each
    ended hold's activities are queued on the actor's inbox in number order,
    for the caller to replay (SYNC-21-013).  Returns how many holds ended.

    The sweep is one act (ADR-0176): it takes the tree lock, then reads
    *clock* once, and judges every hold against that instant.  The replay
    of what it releases is not part of it; each replayed activity is an act
    of its own.
    """
    with open_act(clock) as at:
        count = end_expired_sender_sequence_holds(
            cast(CasePersistence, actor_dl),
            at,
            get_config().ledger.sender_sequence_hold,
        )
    if count:
        logger.info(
            "Ended %d sender-sequence hold(s) whose wait passed for actor"
            " '%s' (SYNC-21-011)",
            count,
            getattr(actor_dl, "actor_id", None),
        )
    queue_due_held_activities(actor_dl)
    return count


async def end_hosted_expired_holds(
    emitter: ActivityEmitter | None = None,
) -> int:
    """End every hosted actor's expired holds and replay what they release.

    Each actor's store is its own (ADR-0073), worked on under its inbox
    lock, off the event loop, with the replay that follows
    (:func:`run_actor_work_then_replay`).  An actor whose work raises is
    logged, and the next actor is still worked on; its holds stay for the
    next round.

    Production-only, as the startup replay is: it runs only in the
    single-node production lifespan, so ``hosted_actor_ids()`` and
    ``get_datalayer`` are the node's own (DL-07-011).

    Returns:
        The number of holds ended across every hosted actor.
    """
    total = 0
    clock = SystemClock()
    for actor_id in actor_hosts.hosted_actor_ids():
        try:
            actor_dl = get_datalayer(actor_id)
            ended: list[int] = []
            await run_actor_work_then_replay(
                actor_dl,
                actor_id,
                None,
                emitter,
                partial(_end_expired_holds_into, actor_dl, clock, ended),
            )
            total += sum(ended)
        except Exception:
            # The timer boundary: one actor's failure must not stop the
            # others' or the server.  Its holds stay for the next round.
            logger.exception(
                "Ending expired sender-sequence holds raised for actor_id=%s"
                " (SYNC-21-011).",
                actor_id,
            )
    return total


@dataclass
class SenderSequenceHoldTimer:
    """The running hold timer: its task and its stop signal."""

    task: "asyncio.Task[None]"
    stop: asyncio.Event


async def _end_holds_on_interval(
    emitter: ActivityEmitter | None,
    interval_seconds: float,
    stop: asyncio.Event,
) -> None:
    """End expired holds every *interval_seconds* until *stop* is set."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            try:
                await end_hosted_expired_holds(emitter=emitter)
            except Exception:
                logger.exception(
                    "Sender-sequence hold timer round raised (SYNC-21-011)."
                )


def start_sender_sequence_hold_timer(
    emitter: ActivityEmitter | None,
) -> SenderSequenceHoldTimer:
    """Start the hold timer as a task beside the server (SYNC-21-011).

    It checks every quarter of ``ledger.sender_sequence_hold_seconds``.
    """
    interval = get_config().ledger.sender_sequence_hold_seconds / 4
    stop = asyncio.Event()
    return SenderSequenceHoldTimer(
        task=asyncio.create_task(
            _end_holds_on_interval(emitter, interval, stop)
        ),
        stop=stop,
    )


async def finish_sender_sequence_hold_timer(
    timer: SenderSequenceHoldTimer | None,
) -> None:
    """Stop the hold timer at shutdown, if it was started.

    Signalled and waited for, not cancelled, as the position statements
    are: a round in progress finishes, under the actor's lock.
    """
    if timer is None:
        return
    timer.stop.set()
    await timer.task


__all__ = [
    "SenderSequenceHoldTimer",
    "end_expired_holds",
    "end_hosted_expired_holds",
    "finish_sender_sequence_hold_timer",
    "start_sender_sequence_hold_timer",
]
