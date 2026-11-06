#!/usr/bin/env python
"""Replay every hosted actor's inbox queue when the process starts (IE-06-006).

An item left queued by a previous run, for example by a process stop during
its replay attempt (IE-06-005), is otherwise replayed only when the next
delivery reaches the same actor, which may never happen.  The app lifespan
starts :func:`replay_hosted_inbox_queues` once at startup
(:func:`start_startup_inbox_replay`), as a task beside
the server, so a slow replay or outbox drain never holds back readiness.  It
re-runs what is queued, with the bounded retry and dead letter of a replay
after a delivery (IE-06-004).

Before the queue, it runs again every message a run left in holding with no
verdict (:func:`rerun_left_in_holding`): a process stop mid-run leaves the
message's record in holding, so each such record is a run to finish
(ADR-0154, CLP-10-074).  The records are listed outside the actor's lock, so
a delivery may settle one first; its seen-before door then answers the
re-run, which does nothing.  The held body is
routed as a resend of itself, so the seen-before door lets it through, its
intake marks the record ``HANDLED`` and every stage that answers a delivery
once reads the run as a re-run.
"""

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

import asyncio
import json
import logging
from typing import cast

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    replay_inbox_queue,
    run_inbox_pipeline,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.core.ports.emitter import ActivityEmitter
from vultron.core.services.received_activity import sealed_body_of
from vultron.core.services.received_holding import records_left_in_holding

logger = logging.getLogger(__name__)


async def rerun_left_in_holding(
    actor_dl: DataLayer,
    actor_id: str,
    dispatcher: ActivityDispatcher | None,
    emitter: ActivityEmitter | None,
) -> int:
    """Run again each message a run left in holding for *actor_id*.

    Each record is run as the delivery of the body it holds, through the
    same pipeline and per-actor lock as a delivery
    (:func:`~vultron.adapters.driving.fastapi.inbox_orchestration.run_inbox_pipeline`),
    so it reaches its outcome as any re-run does: the handling tree runs
    again from the body, nothing its first run kept is done twice, and the
    outcome stage archives or stubs it (ADR-0154, CLP-10-074).  A record a
    delivery settled meanwhile is answered by its seen-before door.

    A record whose re-run raises is logged at ERROR and stays in holding for
    the next start; the records after it are still run, and so is the
    actor's queue replay after this returns.

    Returns the number of records run again without raising.
    """
    records = records_left_in_holding(cast(CasePersistence, actor_dl))
    finished = 0
    for record in records:
        logger.info(
            "Running again activity '%s' for actor_id=%s, left in holding"
            " with no verdict by an earlier run (ADR-0154, CLP-10-074).",
            record.activity_id,
            actor_id,
        )
        try:
            await run_inbox_pipeline(
                json.loads(sealed_body_of(record)),
                actor_dl,
                actor_id,
                dispatcher,
                emitter,
            )
        except Exception:
            # One record's failure must not keep the others, or the queue,
            # from running; the record stays in holding (CLP-10-074).
            logger.exception(
                "Re-run of activity '%s' for actor_id=%s raised; it stays in"
                " holding for the next start (CLP-10-074).",
                record.activity_id,
                actor_id,
            )
            continue
        finished += 1
    return finished


async def replay_hosted_inbox_queues(
    emitter: ActivityEmitter | None = None,
) -> int:
    """Replay the inbox queue of every actor this node hosts.

    Actors are found from the stores that exist
    (:func:`~vultron.adapters.driven.actor_hosts.hosted_actor_ids`), each
    replayed from its own store (ADR-0073: there is no store that sees
    every actor's rows).  Each actor's queue is replayed under that
    actor's inbox lock and off the event loop
    (:func:`~vultron.adapters.driving.fastapi.inbox_orchestration.replay_inbox_queue`).
    An actor whose replay raises is logged, and the next actor is still
    replayed; its items stay queued for the next replay (IE-06-005).

    Production-only: it runs only in the single-node production lifespan
    (``configure_globals=True``), where the configured ``db_url`` and base URL
    are the node's own.  That is why it calls ``hosted_actor_ids()`` and
    ``get_datalayer`` unscoped; an app built by ``create_app`` never starts it,
    so no other deployment in the process is read (DL-07-011).

    Args:
        emitter: The app's ActivityEmitter, for the outbox drain after each
            actor's replay.

    Returns:
        The number of actors whose queue held an item.
    """
    replayed = 0
    for actor_id in actor_hosts.hosted_actor_ids():
        try:
            actor_dl = get_datalayer(actor_id)
            await rerun_left_in_holding(actor_dl, actor_id, None, emitter)
            queued = len(actor_dl.inbox_list())
            if not queued:
                continue
            replayed += 1
            logger.info(
                "Replaying %d queued inbox item(s) for actor_id=%s at startup"
                " (IE-06-006).",
                queued,
                actor_id,
            )
            await replay_inbox_queue(actor_dl, actor_id, None, emitter)
        except Exception:
            # The startup boundary: one actor's failed replay must not stop
            # the others' or the server's start.  The attempt rolled back,
            # so its item is still queued (IE-06-005).
            logger.exception(
                "Startup inbox replay raised for actor_id=%s; its items stay"
                " queued for the next replay (IE-06-006).",
                actor_id,
            )
    return replayed


def start_startup_inbox_replay(
    emitter: ActivityEmitter | None,
) -> "asyncio.Task[int]":
    """Start the startup replay as a task beside the server (IE-06-006).

    A task, not an await before the lifespan yields: the replay runs every
    retry and an outbox drain, and awaited it would hold back readiness for
    as long as an unreachable peer takes to time out.  The per-actor inbox
    lock orders it with any delivery that arrives meanwhile.
    """
    return asyncio.create_task(replay_hosted_inbox_queues(emitter=emitter))


async def finish_startup_inbox_replay(
    task: "asyncio.Task[int] | None",
) -> None:
    """Wait for the startup replay at shutdown, if one was started.

    Waited for, not cancelled: a cancelled await would leave its worker
    thread running an attempt with the actor's lock released.
    """
    if task is not None:
        await task
