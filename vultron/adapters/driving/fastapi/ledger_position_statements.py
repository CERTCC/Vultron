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

from vultron.adapters.driven.actor_hosts import CONFIGURED_NODE, NodeDeployment
from vultron.adapters.driven.clock import act_clock
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
from vultron.errors import VultronConfigScopeLostError

logger = logging.getLogger(__name__)


def _state_positions(
    actor_dl: SqliteDataLayer, actor_id: str, sent: list[int]
) -> None:
    """Queue *actor_id*'s statements; append how many to *sent*."""
    sent.append(
        state_ledger_positions_trigger(
            actor_dl, actor_id, SyncActivityAdapter(actor_dl), act_clock()
        )
    )


async def state_hosted_ledger_positions(
    emitter: ActivityEmitter | None = None,
    *,
    node: NodeDeployment = CONFIGURED_NODE,
) -> int:
    """State the ledger positions of every actor this node hosts, once.

    Each actor's statements are built from its own store (ADR-0073) under its
    inbox lock, so they never interleave with a delivery to it, and its
    outbox is drained after (:func:`run_serialised_actor_work`).  An actor
    whose statements raise is logged, and the next actor still states its
    own.

    Only *node*'s stores are read (DL-07-011).  The production lifespan
    passes the configured node; an app holding its own config passes its own
    deployment (ADR-0206), so no other node's stores in the process are read.
    A ``VultronConfigScopeLostError`` means the work lost its app's config
    scope, which is no one actor's failure, so it is raised, not logged
    (ADR-0206).  Any other ``VultronWiringError`` stays one actor's failure.

    Args:
        emitter: The app's ActivityEmitter, for the outbox drain.
        node: The deployment whose hosted actors state their positions.

    Returns:
        The number of statements queued across every hosted actor.
    """
    total = 0
    for actor_id in node.actor_ids():
        try:
            actor_dl = node.store(actor_id)
            sent: list[int] = []
            await run_serialised_actor_work(
                actor_dl,
                actor_id,
                emitter,
                partial(_state_positions, actor_dl, actor_id, sent),
            )
            total += sum(sent)
        except VultronConfigScopeLostError:
            raise
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

    task: asyncio.Task[None]
    stop: asyncio.Event


async def _one_round(
    emitter: ActivityEmitter | None, node: NodeDeployment
) -> None:
    """State every hosted actor's positions once, raising only a wiring error.

    A failure outside one actor's statements, such as listing the hosted
    actors, is logged and the round ends; the next round tries again, so an
    error never ends the interval loop.  A ``VultronConfigScopeLostError``
    (the work lost its app's config scope, ADR-0206) ends the task, and
    surfaces when it is awaited at shutdown.
    """
    try:
        await state_hosted_ledger_positions(emitter=emitter, node=node)
    except VultronConfigScopeLostError:
        raise
    except Exception:
        logger.exception(
            "Ledger position statement round raised (SYNC-17-007)."
        )


async def _state_positions_then_repeat(
    emitter: ActivityEmitter | None,
    interval_seconds: int | None,
    stop: asyncio.Event,
    after: asyncio.Task[int] | None,
    node: NodeDeployment,
) -> None:
    """State positions after the restart, then on the interval, if set.

    The first round waits for *after*, the startup inbox replay, so the
    position a participant states includes every entry its queue held
    (IE-06-006); a replay that failed is the replay's to report.  A shutdown
    signalled while it waits ends the task with no round: a server told to
    stop starts no new statements or outbox drains.
    """
    if after is not None:
        await asyncio.wait({after})
        if stop.is_set():
            return
    await _one_round(emitter, node)
    if interval_seconds is None:
        return
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            await _one_round(emitter, node)


def start_ledger_position_statements(
    emitter: ActivityEmitter | None,
    after: asyncio.Task[int] | None = None,
    *,
    node: NodeDeployment = CONFIGURED_NODE,
) -> PositionStatements:
    """Start the position statements as a task beside the server.

    A task, so the statements and their outbox drain never hold back
    readiness.  The first round runs once *after* (the startup inbox replay)
    is done.  The interval is read from
    ``ledger.position_statement_interval_seconds`` (off by default), in the
    caller's config scope: an app holding its own config reads its own
    (ADR-0206).  Only *node*'s hosted actors state positions.
    """
    interval = get_config().ledger.position_statement_interval_seconds
    stop = asyncio.Event()
    return PositionStatements(
        task=asyncio.create_task(
            _state_positions_then_repeat(emitter, interval, stop, after, node)
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
