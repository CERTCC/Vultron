#!/usr/bin/env python
"""State each hosted participant's ledger positions (SYNC-17-007, ADR-0155).

A participant that missed the last ``Announce(CaseLedgerEntry)`` before a
quiet period, for example because it was down when the entry was sent, gets
no later entry with a gap and so sends no ``Reject``.  It recovers by stating
its position: ``Read(CaseLedgerEntry)`` naming its replica's tail, which the
CASE_MANAGER answers with a replay of the entries it lacks (SYNC-17-004).

The app lifespan starts :func:`start_ledger_position_statements` once at
startup.  The task states every hosted actor's positions after the restart,
and, when ``ledger.position_statement_interval_seconds`` is set, again on that
interval.  The interval is off by default (``None``): a periodic check costs
traffic a deployment should choose (SYNC-17-007).
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
import logging
from dataclasses import dataclass
from functools import partial
from typing import Any

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    run_serialised_actor_work,
)
from vultron.config.app import get_config
from vultron.core.ports.emitter import ActivityEmitter
from vultron.core.use_cases.triggers.sync import (
    state_ledger_positions_trigger,
)

logger = logging.getLogger(__name__)


def _state_positions(
    actor_dl: SqliteDataLayer, actor_id: str, sent: list[int]
) -> None:
    """Queue *actor_id*'s statements; append how many to *sent*."""
    sent.append(
        state_ledger_positions_trigger(
            actor_dl, actor_id, SyncActivityAdapter(actor_dl)
        )
    )


async def state_hosted_ledger_positions(
    emitter: ActivityEmitter | None = None,
) -> int:
    """State the ledger positions of every actor this node hosts, once.

    Each actor's statements are built from its own store (ADR-0073) under its
    inbox lock, so they never interleave with a delivery to it, and its
    outbox is drained after (:func:`run_serialised_actor_work`).  An actor
    whose statements raise is logged, and the next actor still states its
    own.

    Args:
        emitter: The app's ActivityEmitter, for the outbox drain.

    Returns:
        The number of statements queued across every hosted actor.
    """
    total = 0
    for actor_id in actor_hosts.hosted_actor_ids():
        try:
            actor_dl = get_datalayer(actor_id)
            sent: list[int] = []
            await run_serialised_actor_work(
                actor_dl,
                actor_id,
                emitter,
                partial(_state_positions, actor_dl, actor_id, sent),
            )
            total += sum(sent)
        except Exception:
            # The statement boundary: one actor's failure must not stop the
            # others' or the server.  Nothing was committed; the next
            # statement tries again.
            logger.exception(
                "Ledger position statements raised for actor_id=%s"
                " (SYNC-17-007).",
                actor_id,
            )
    return total


@dataclass
class PositionStatements:
    """The running position statements: their task and its stop signal."""

    task: "asyncio.Task[None]"
    stop: asyncio.Event


async def _one_round(emitter: ActivityEmitter | None) -> None:
    """State every hosted actor's positions once, never raising.

    A failure outside one actor's statements, such as listing the hosted
    actors, is logged and the round ends; the next round tries again, so an
    error never ends the interval loop or surfaces at shutdown.
    """
    try:
        await state_hosted_ledger_positions(emitter=emitter)
    except Exception:
        logger.exception(
            "Ledger position statement round raised (SYNC-17-007)."
        )


async def _state_positions_then_repeat(
    emitter: ActivityEmitter | None,
    interval_seconds: int | None,
    stop: asyncio.Event,
    after: "asyncio.Task[Any] | None",
) -> None:
    """State positions after the restart, then on the interval, if set.

    The first round waits for *after*, the startup inbox replay, so the
    position a participant states includes every entry its queue held
    (IE-06-006); a replay that failed is the replay's to report.
    """
    if after is not None:
        await asyncio.wait({after})
    await _one_round(emitter)
    if interval_seconds is None:
        return
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            await _one_round(emitter)


def start_ledger_position_statements(
    emitter: ActivityEmitter | None,
    after: "asyncio.Task[Any] | None" = None,
) -> PositionStatements:
    """Start the position statements as a task beside the server.

    A task, so the statements and their outbox drain never hold back
    readiness.  The first round runs once *after* (the startup inbox replay)
    is done.  The interval is read from
    ``ledger.position_statement_interval_seconds`` (off by default).
    """
    interval = get_config().ledger.position_statement_interval_seconds
    stop = asyncio.Event()
    return PositionStatements(
        task=asyncio.create_task(
            _state_positions_then_repeat(emitter, interval, stop, after)
        ),
        stop=stop,
    )


async def finish_ledger_position_statements(
    statements: PositionStatements | None,
) -> None:
    """Stop the position statements at shutdown, if they were started.

    Signalled and waited for, not cancelled: a cancelled await would leave
    its worker thread building statements with the actor's lock released,
    as the startup inbox replay explains.  A round in progress finishes;
    the interval wait ends at once.
    """
    if statements is None:
        return
    statements.stop.set()
    await statements.task
