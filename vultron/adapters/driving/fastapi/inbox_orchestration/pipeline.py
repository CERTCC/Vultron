"""The inbox background task: one serialised pipeline run per actor.

:func:`run_inbox_pipeline` builds the ingress, dispatch and queue adapters
for one delivery and hands them to
:func:`~vultron.core.behaviors.inbox.process_payload` under the receiving
actor's lock; :func:`replay_inbox_queue` drains the actor's inbox queue the
same way (IO-03-001, IO-03-003, IE-06-004).
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
from collections.abc import Callable
from typing import Any, cast

from vultron.adapters.driven.http_object_fetch import ObjectFetcher
from vultron.adapters.driving.fastapi import inbox_port_factories
from vultron.adapters.driving.fastapi.inbox_dereference import (
    FastAPIDereferencePort,
    resolve_open_fetches,
)
from vultron.adapters.driving.fastapi.inbox_orchestration.ingress import (
    FastAPIIngressAdapter,
)
from vultron.adapters.driving.fastapi.inbox_orchestration.ports import (
    FastAPIDispatchAdapter,
    FastAPIQueuePort,
    FastAPIReceivedOutcomePort,
)
from vultron.adapters.driving.fastapi.inbox_queue_drain import (
    drain_inbox_queue,
    log_if_rejected,
)
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.adapters.inbox_staging import (
    InlineObjectStaging,
)
from vultron.config import get_config
from vultron.core.behaviors.inbox import process_payload
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.core.ports.emitter import ActivityEmitter

logger = logging.getLogger(__name__)


# Per-actor asyncio locks that serialise concurrent inbox background tasks.
# When multiple HTTP POSTs arrive for the same actor simultaneously, each
# creates a separate asyncio Task (BackgroundTask).  Without serialisation,
# the second task's process_payload can run before the first has stored its
# ledger entry, causing a hash-chain mismatch → spurious Reject → Replay loop
# that may not converge within the demo timeout (issue #1525).
_actor_inbox_locks: dict[str, asyncio.Lock] = {}


def _get_actor_lock(actor_id: str) -> asyncio.Lock:
    """Return the per-actor asyncio.Lock for *actor_id*, creating it on first use."""
    if actor_id not in _actor_inbox_locks:
        _actor_inbox_locks[actor_id] = asyncio.Lock()
    return _actor_inbox_locks[actor_id]


class _InboxRun:
    """The adapters one inbox run of an actor shares (IO-03-003).

    The ingress adapter and the queue port share one staging, so a delivery
    the queue defers is held whole for its replay.
    """

    def __init__(
        self,
        actor_dl: DataLayer,
        actor_id: str,
        dispatcher: ActivityDispatcher | None,
    ) -> None:
        self.actor_dl = actor_dl
        self.actor_id = actor_id
        self.staging = InlineObjectStaging(actor_dl)
        self.ingress = FastAPIIngressAdapter(dl=actor_dl, staging=self.staging)
        self.dispatch = FastAPIDispatchAdapter(
            dl=actor_dl, actor_id=actor_id, dispatcher=dispatcher
        )
        self.queue = FastAPIQueuePort(
            dl=actor_dl,
            actor_dl=cast(DataLayer, actor_dl),
            staging=self.staging,
        )
        # Shares the staging too: an activity waiting on a fetch is held
        # whole for its replay, as a deferred one is (AKM-05-007).
        self.dereference = FastAPIDereferencePort(
            actor_dl, actor_id, self.staging
        )
        # The final outcome stage's one write: a refused delivery's body is
        # given up for a receipt stub (CLP-10-018, ADR-0154).
        self.outcome = FastAPIReceivedOutcomePort(actor_dl)
        # The receiving actor's RSVP windows govern inbound embargo invites
        # (EP-07-001, EP-07-002); None applies the protocol defaults.
        self.actor_config = inbox_port_factories._resolve_actor_config()
        self.max_attempts = get_config().max_inbox_retry_attempts

    def drain_queue(self) -> None:
        """Replay every item queued in the actor's inbox (IE-06-004)."""
        drain_inbox_queue(
            self.actor_dl,
            self.actor_id,
            self.dispatch,
            self.queue,
            self.staging,
            self.actor_config,
            self.max_attempts,
            self.dereference,
            self.outcome,
        )


async def _run_serialised(
    actor_dl: DataLayer,
    actor_id: str,
    emitter: ActivityEmitter | None,
    work: Callable[[], None],
) -> None:
    """Run *work* under the actor's inbox lock, off the loop, then drain.

    Off the event loop, deliberately.  Starlette runs an ``async``
    background task on the loop itself, and ``process_payload`` is
    synchronous — BT ticks, the BT global lock, SQLite I/O.  Called inline
    it stalls the whole container for every inbound activity: no HTTP
    response goes out, no delivery from a peer is accepted, the co-hosted
    OutboxMonitor coroutine cannot drain, and a trigger route waiting on the
    BT lock from its threadpool thread starves (IE-06-002, IE-06-003,
    BT-11-002).  The rv/rcvcv demo flakes were the CaseActor's outbox paying
    one full BT tick per delivery on the vendor container (#3033, #2898).
    ``asyncio.to_thread`` matches what the sync trigger routes already do;
    the BT global RLock serialises BT execution across threads, and the
    per-actor lock (held across the thread hop) keeps this actor's
    deliveries FIFO (BT-11-001, #1525): process_payload for entry N+1 never
    starts before entry N has been stored, or the hash-chain check fails and
    a spurious Reject follows.
    """
    try:
        async with _get_actor_lock(actor_id):
            await asyncio.to_thread(work)
    finally:
        # The delivery's replies, and any fault a settled replay queued, are
        # already in the outbox: a store write that raised while settling a
        # replay must not leave them undelivered.
        await outbox_handler(actor_id, actor_dl, emitter=emitter)


async def run_serialised_actor_work(
    actor_dl: DataLayer,
    actor_id: str,
    emitter: ActivityEmitter | None,
    work: Callable[[], None],
) -> None:
    """Run *work* as this actor's deliveries run: serialised, then drained.

    For actor-initiated work that is not a delivery, such as the ledger
    position statements a participant sends after a restart (SYNC-17-007).
    It takes the actor's inbox lock, so it never interleaves with a delivery
    being processed, runs off the event loop, and drains the outbox after
    (see :func:`_run_serialised`).
    """
    await _run_serialised(actor_dl, actor_id, emitter, work)


async def run_inbox_pipeline(
    payload: dict[str, Any] | bytes | str | Any,
    actor_dl: DataLayer,
    actor_id: str,
    dispatcher: ActivityDispatcher | None,
    emitter: ActivityEmitter | None,
    fetcher: ObjectFetcher | None = None,
) -> None:
    """Adapter-layer background task: construct adapters and run pipeline.

    Calls :func:`~vultron.core.behaviors.inbox.process_payload` for the
    immediate payload, then replays every activity queued in the inbox
    (e.g., after bootstrap dispatch) with bounded retry and dead letter
    (:func:`~vultron.adapters.driving.fastapi.inbox_queue_drain.drain_inbox_queue`,
    IE-06-004), and finally drains the outbox.  Last, it makes every fetch
    an activity waits on and replays the activities each one settles
    (:func:`~vultron.adapters.driving.fastapi.inbox_dereference.resolve_open_fetches`,
    AKM-05-007).
    The synchronous BT work runs in a worker thread so the ASGI event loop
    keeps serving while a handler executes (IE-06-002, BT-11-002); only the
    outbox drain, which is async I/O, runs on the loop.

    This function is the background task scheduled by ``post_actor_inbox``.
    It and the startup replay (:func:`replay_inbox_queue`) construct the
    adapter instances, through :class:`_InboxRun` (IO-03-003).

    Args:
        payload: Raw inbox payload (JSON body dict or as_Activity).
        actor_dl: The receiving actor's DataLayer — ingress, dispatch, queues
            and stored activities alike.  Before ADR-0073 a separate shared
            DataLayer was threaded alongside it; the two only differed because
            the shared pool could see every actor's rows.
        actor_id: Canonical URI of the receiving actor.
        dispatcher: Optional per-app dispatcher.
        emitter: Optional per-app ActivityEmitter.
        fetcher: The object fetcher; ``None`` uses the HTTP one.
    """
    run = _InboxRun(actor_dl, actor_id, dispatcher)

    def _process_and_replay() -> None:
        """The synchronous BT work for one delivery, plus its replays.

        Runs on a worker thread (see :func:`_run_serialised`), so it must not
        touch asyncio.
        """
        outcome = process_payload(
            payload,
            run.ingress,
            run.dispatch,
            run.queue,
            actor_config=run.actor_config,
            dereference_port=run.dereference,
            received_outcome_port=run.outcome,
        )
        logger.debug(
            "run_inbox_pipeline: status=%s context_id=%s",
            outcome.status,
            outcome.context_id,
        )
        log_if_rejected(outcome, actor_id, replayed=False)

        # Replay what this delivery, or an earlier one, queued: activities
        # pushed back by the post-bootstrap replay, and held ledger
        # Announces replayed once their entry applies (SYNC-14-009).
        run.drain_queue()

    await _run_serialised(actor_dl, actor_id, emitter, _process_and_replay)
    await _resolve_fetches(run, emitter, fetcher)


async def _resolve_fetches(
    run: _InboxRun,
    emitter: ActivityEmitter | None,
    fetcher: ObjectFetcher | None,
) -> None:
    """Make *run*'s open fetches, settling each under the actor's lock."""

    async def _locked(work: Callable[[], None]) -> None:
        await _run_serialised(run.actor_dl, run.actor_id, emitter, work)

    await resolve_open_fetches(
        run.actor_dl, run.actor_id, _locked, run.drain_queue, fetcher
    )


async def replay_inbox_queue(
    actor_dl: DataLayer,
    actor_id: str,
    dispatcher: ActivityDispatcher | None,
    emitter: ActivityEmitter | None,
    fetcher: ObjectFetcher | None = None,
) -> None:
    """Replay every item queued in *actor_id*'s inbox, with no delivery.

    The startup replay (IE-06-006): the same drain, bounded retry and dead
    letter as a replay after a delivery (IE-06-004), under the same
    per-actor lock as :func:`run_inbox_pipeline` and off the event loop
    (IE-06-003), then the outbox drain.  A fetch an earlier run left open
    is made then, so an activity waiting on it does not wait for the next
    delivery (AKM-05-007).

    Args:
        actor_dl: The receiving actor's DataLayer, which holds the queue.
        actor_id: Canonical URI of the receiving actor.
        dispatcher: Optional per-app dispatcher.
        emitter: Optional per-app ActivityEmitter.
        fetcher: The object fetcher; ``None`` uses the HTTP one.
    """
    run = _InboxRun(actor_dl, actor_id, dispatcher)
    await _run_serialised(actor_dl, actor_id, emitter, run.drain_queue)
    await _resolve_fetches(run, emitter, fetcher)
