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

"""Background outbox-drain loop (OUTBOX-MON-1).

Implements an ``OutboxMonitor`` that drains all registered actor-scoped
DataLayer instances when woken by an enqueue notification — or after a
safety-net polling interval elapses with no notification.

The monitor is started inside the FastAPI lifespan (``app.py``) and runs as
a background asyncio task for the lifetime of the process.  Stopping the
monitor (at shutdown) cancels the task cleanly.

Spec coverage:
- OUTBOX-MON-1: Background outbox-drain loop; periodically drains all
  actor outboxes without a manual trigger.
- OX-09-001: Monitor wakes immediately on enqueue via callback.
- OX-09-002: Safety-net poll interval retained for missed notifications.
- OX-09-003: Callback injected as Callable; no monitor import in DL layer.
"""

import asyncio
import logging
from collections.abc import Callable

from vultron.adapters.driven.datalayer import (
    get_all_actor_datalayers,
    get_datalayer,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.emitter import ActivityEmitter

logger = logging.getLogger(__name__)


class OutboxMonitor:
    """Background outbox-drain loop for all registered actors (OUTBOX-MON-1).

    Wakes immediately when any actor enqueues an outbox item (via injected
    callback) and drains all pending outboxes.  A safety-net polling interval
    ensures eventual delivery even when a notification is missed.

    Lifecycle::

        monitor = OutboxMonitor()
        monitor.start()   # call from within a running asyncio event loop
        ...
        monitor.stop()    # call at shutdown

    The ``actor_datalayers_factory`` and ``emitter`` parameters allow
    injection of test doubles without patching module globals.

    Args:
        poll_interval: Maximum seconds between drain passes (default 1.0).
            The monitor may drain more frequently when actors enqueue items.
        actor_datalayers_factory: Callable returning the current
            ``{actor_id: DataLayer}`` mapping.  Defaults to
            :func:`~vultron.adapters.driven.datalayer_sqlite.get_all_actor_datalayers`.
        shared_dl: Shared/admin DataLayer used to resolve actor records and
            read activity objects.  Defaults to ``get_datalayer()`` (no
            actor scope).  When the shared DL is a
            :class:`~vultron.adapters.driven.datalayer_sqlite.SqliteDataLayer`
            the monitor also registers its wakeup callback there so that
            ``record_outbox_item`` calls on the shared DL trigger immediate
            wakeup.
        emitter: ``ActivityEmitter`` implementation for HTTP delivery.
            Defaults to ``DeliveryQueueAdapter`` (resolved inside
            :func:`outbox_handler`).
    """

    def __init__(
        self,
        poll_interval: float = 1.0,
        actor_datalayers_factory: (
            Callable[[], dict[str, SqliteDataLayer]] | None
        ) = None,
        shared_dl: DataLayer | None = None,
        emitter: ActivityEmitter | None = None,
    ) -> None:
        self._poll_interval = poll_interval
        self._actor_datalayers_factory = actor_datalayers_factory
        self._shared_dl = shared_dl
        self._emitter = emitter
        self._task: asyncio.Task | None = None
        self._running = False
        self._wakeup_event: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._registered_actors: set[str] = set()

    async def drain_all(self) -> None:
        """Process all registered actor outboxes once.

        Skips actors whose outbox is empty.  Delivery errors for a single
        actor are caught, logged at ERROR level, and do not abort processing
        for other actors.
        """
        factory = (
            self._actor_datalayers_factory
            if self._actor_datalayers_factory is not None
            else get_all_actor_datalayers
        )
        actor_dls = factory()
        shared_dl = (
            self._shared_dl if self._shared_dl is not None else get_datalayer()
        )

        for actor_id, dl in actor_dls.items():
            if not dl.outbox_list():
                continue
            try:
                await outbox_handler(
                    actor_id,
                    dl,
                    shared_dl=shared_dl,
                    emitter=self._emitter,
                )
            except Exception as exc:
                logger.error(
                    "OutboxMonitor: unhandled error draining outbox"
                    " for actor '%s': %s",
                    actor_id,
                    exc,
                )

    def _notify(self, actor_id: str) -> None:
        """Wakeup callback — called by SqliteDataLayer when an item is enqueued.

        Safe to call from any thread (uses :meth:`asyncio.loop.call_soon_threadsafe`
        so it is compatible with both on-loop and off-loop callers).

        Args:
            actor_id: The actor whose outbox received a new item.
        """
        if self._wakeup_event is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self._wakeup_event.set)

    def _register_new_actors(self) -> None:
        """Register _notify with any newly seen SqliteDataLayer instances.

        Called once at loop startup and again after each drain pass to pick
        up actors that were registered while the monitor was running.  Also
        registers the shared DataLayer so that ``record_outbox_item`` calls
        on it trigger immediate wakeup.
        """
        factory = (
            self._actor_datalayers_factory
            if self._actor_datalayers_factory is not None
            else get_all_actor_datalayers
        )
        actor_dls = factory()
        for actor_id, dl in actor_dls.items():
            if actor_id not in self._registered_actors and isinstance(
                dl, SqliteDataLayer
            ):
                dl.set_enqueue_callback(self._notify)
                self._registered_actors.add(actor_id)

        # Also register with the shared DL so record_outbox_item wakes us.
        shared_dl = (
            self._shared_dl if self._shared_dl is not None else get_datalayer()
        )
        if "_shared_" not in self._registered_actors and isinstance(
            shared_dl, SqliteDataLayer
        ):
            shared_dl.set_enqueue_callback(self._notify)
            self._registered_actors.add("_shared_")

    async def _run_loop(self) -> None:
        """Main drain loop — wakes on enqueue or safety-net timeout."""
        logger.info(
            "OutboxMonitor started (poll_interval=%.1fs).",
            self._poll_interval,
        )
        event = self._wakeup_event
        assert event is not None  # guaranteed by start()
        self._register_new_actors()
        try:
            while self._running:
                try:
                    await asyncio.wait_for(
                        event.wait(), timeout=self._poll_interval
                    )
                except asyncio.TimeoutError:
                    pass
                event.clear()
                self._register_new_actors()
                await self.drain_all()
        except asyncio.CancelledError:
            pass
        logger.info("OutboxMonitor stopped.")

    def start(self) -> None:
        """Start the background drain loop as an asyncio task.

        Must be called from within a running asyncio event loop (e.g.,
        inside a FastAPI lifespan coroutine).  Calling ``start()`` while
        the monitor is already running is a no-op (logged at WARNING level).
        """
        if self._task is not None and not self._task.done():
            logger.warning(
                "OutboxMonitor.start() called while already running;"
                " ignoring."
            )
            return
        self._loop = asyncio.get_running_loop()
        self._wakeup_event = asyncio.Event()
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    def stop(self) -> None:
        """Signal the drain loop to stop and cancel the asyncio task.

        Safe to call even if the monitor was never started.
        """
        self._running = False
        self._loop = None
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None
        self._registered_actors.clear()
