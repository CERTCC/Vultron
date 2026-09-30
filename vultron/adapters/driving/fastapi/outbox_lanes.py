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

"""Per-recipient delivery lanes for one actor's outbox (ADR-0112).

An outbox is one FIFO of activity ids, but the order that matters to a
recipient is the order of the rows addressed to *it*: a ledger fan-out is one
``Announce`` per participant, and a replica that receives entry ``N+1`` before
entry ``N`` buffers a forward gap and sends a ``Reject`` (SYNC-14-002), which
the CASE_MANAGER answers by replaying the whole suffix into the same queue
(#3602, #3033, #2898).

This module schedules one drain pass as **lanes**: every recipient a row is
addressed to is a lane, a row runs only when none of its lanes has a row in
flight or a row waiting ahead of it, and distinct lanes proceed concurrently
(OX-01-005, OX-01-006).  A row whose delivery fails past the per-pass cap
*stalls* its lanes: nothing behind it in those lanes is attempted this pass,
and the stalled rows are handed back for re-queueing in enqueue order
(OX-13-012, #3878).

The scheduler knows nothing about HTTP or retry bookkeeping — the caller
supplies ``deliver`` and receives the ids to re-queue.
"""

import asyncio
import enum
import logging
from collections.abc import Awaitable, Callable

from vultron.adapters.driving.fastapi.outbox_addressing import (
    _extract_recipients,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


class RowOutcome(enum.Enum):
    """What one row's delivery attempt (including in-pass retries) came to."""

    DELIVERED = "delivered"
    #: Exhausted its total attempt budget and was dead-lettered; the row is
    #: gone, so its lanes are released (OX-13-009).
    DEAD_LETTERED = "dead_lettered"
    #: Failed past the per-pass cap; the row goes back to the queue and its
    #: lanes carry nothing further this pass (OX-13-011, OX-13-012).
    STALLED = "stalled"


DeliverRow = Callable[[str], Awaitable[RowOutcome]]


def lane_keys(activity_id: str, dl: DataLayer) -> frozenset[str]:
    """Return the lanes *activity_id* occupies: its recipients (OX-01-005).

    Resolved from the sealed body before delivery.  A row whose body cannot be
    read, or that names no recipient, has no recipient order to preserve; it
    gets a lane of its own so it neither waits for nor holds up anything, and
    ``handle_outbox_item`` reports it when it is popped.
    """
    try:
        body = read_sealed_body_dict(dl, activity_id)
    except Exception:  # a read fault is the delivery step's to report
        body = None
    recipients = _extract_recipients(body) if body is not None else []
    if not recipients:
        return frozenset({f"?{activity_id}"})
    return frozenset(recipients)


class StallOrder:
    """Enqueue order of the rows a drain has stalled, kept across its passes.

    A stalled row is re-queued at the tail of the persistent FIFO, behind any
    row a producer appended while the pass ran.  Re-queueing every row of a
    stalled lane in *this* order — first stalled first, later arrivals after —
    leaves the queue in the lane's enqueue order for the next pass
    (OX-13-012), which is what a persistent FIFO with tail-only append cannot
    express by itself.
    """

    def __init__(self) -> None:
        self._seq: dict[str, int] = {}

    def add(self, activity_id: str) -> None:
        self._seq.setdefault(activity_id, len(self._seq))

    def __contains__(self, activity_id: object) -> bool:
        return activity_id in self._seq

    def covers(self, activity_ids: list[str]) -> bool:
        """True when every id in *activity_ids* is a stalled row."""
        return all(a in self._seq for a in activity_ids)

    def sort(self, activity_ids: list[str]) -> list[str]:
        """Return *activity_ids* in stall order (all must be stalled)."""
        return sorted(activity_ids, key=self._seq.__getitem__)


class _LaneSchedule:
    """The rows of one batch, moving through waiting → in flight → done/held.

    A lane is *busy* while a row addressed to it is in flight, *blocked* for the
    rest of a scheduling sweep once a waiting row ahead has been passed over,
    and *stalled* for the rest of the pass once a row in it has stalled.
    """

    def __init__(
        self, rows: list[tuple[str, frozenset[str]]], stalled: StallOrder
    ) -> None:
        self.waiting = list(rows)
        self.active: dict[
            asyncio.Task[RowOutcome], tuple[str, frozenset[str]]
        ] = {}
        self._stalled = stalled
        self._busy: set[str] = set()
        self._stalled_lanes: set[str] = {
            lane for aid, lanes in rows if aid in stalled for lane in lanes
        }
        self._held: list[str] = []
        self._finished: set[str] = set()
        self._rows = list(rows)

    def _hold(self, activity_id: str, lanes: frozenset[str]) -> None:
        self._stalled_lanes.update(lanes)
        self._stalled.add(activity_id)
        self._held.append(activity_id)

    def start_ready(self, deliver: DeliverRow) -> None:
        """Start every waiting row whose lanes are all free, in pop order."""
        still: list[tuple[str, frozenset[str]]] = []
        blocked: set[str] = set()
        for activity_id, lanes in self.waiting:
            if lanes & self._stalled_lanes:
                self._hold(activity_id, lanes)
            elif lanes & (self._busy | blocked):
                blocked |= lanes
                still.append((activity_id, lanes))
            else:
                task = asyncio.ensure_future(deliver(activity_id))
                self.active[task] = (activity_id, lanes)
                self._busy |= lanes
        self.waiting = still

    async def wait_one(self) -> None:
        """Wait for at least one in-flight row; free or stall its lanes."""
        done, _ = await asyncio.wait(
            set(self.active), return_when=asyncio.FIRST_COMPLETED
        )
        for task in done:
            activity_id, lanes = self.active.pop(task)
            self._busy -= lanes
            outcome = task.result()  # re-raises a delivery task's exception
            self._finished.add(activity_id)
            if outcome is RowOutcome.STALLED:
                self._hold(activity_id, lanes)

    async def abandon(self) -> list[str]:
        """Cancel every in-flight task; return every row not finished, in order.

        A row whose task raised counts as unfinished — it was neither
        delivered nor dead-lettered — so it goes back to the queue with the
        rows that never started.
        """
        for task in list(self.active):
            task.cancel()
        if self.active:
            await asyncio.gather(*self.active, return_exceptions=True)
        finished_ok = {
            aid
            for task, (aid, _lanes) in self.active.items()
            if not task.cancelled() and task.exception() is None
        } | self._finished
        self.active.clear()
        return [aid for aid, _lanes in self._rows if aid not in finished_ok]

    def hold_remaining(self) -> list[str]:
        """Hold every row still waiting (only stalled lanes can be left) and
        return the held ids in lane enqueue order."""
        for activity_id, lanes in self.waiting:
            self._hold(activity_id, lanes)
        self.waiting = []
        if self._held:
            logger.debug(
                "outbox lanes: %d row(s) held back this pass behind a stalled"
                " lane: %s",
                len(self._held),
                self._held,
            )
        return self._stalled.sort(self._held)


class BatchInterrupted(Exception):
    """A batch did not run to completion; ``undelivered`` lists what to re-queue.

    Raised in place of whatever interrupted the batch — an exception escaping
    a delivery task, or a cancellation of the drain — after every in-flight
    task has been canceled.  ``undelivered`` is every popped row that was
    neither delivered nor dead-lettered, in pop order, so the caller can put
    the rows back before the interruption propagates (OX-01-003).
    """

    def __init__(self, cause: BaseException, undelivered: list[str]) -> None:
        super().__init__(f"{type(cause).__name__}: {cause}")
        self.cause = cause
        self.undelivered = undelivered


async def deliver_batch(
    rows: list[tuple[str, frozenset[str]]],
    deliver: DeliverRow,
    stalled: StallOrder,
) -> list[str]:
    """Deliver one popped batch lane by lane; return the ids to re-queue.

    Args:
        rows: ``(activity_id, lanes)`` in the order popped from the outbox.
        deliver: Delivers one row, including its in-pass retries, and reports
            the outcome.  It is expected not to raise; if it does, the batch
            is interrupted rather than the row silently lost.
        stalled: The drain's record of rows already stalled in an earlier
            batch of this pass; extended with every row stalled or held back
            here.

    Returns:
        The ids to append back to the outbox, in lane enqueue order.

    Raises:
        BatchInterrupted: When a delivery task raised, or the batch was
            canceled; every in-flight task has been canceled and
            ``undelivered`` names the rows to put back.  A cancellation is
            re-raised as ``asyncio.CancelledError`` *after* the caller has
            had the chance to re-queue — see ``_drain_outbox``.
    """
    schedule = _LaneSchedule(rows, stalled)
    try:
        while schedule.waiting or schedule.active:
            schedule.start_ready(deliver)
            if not schedule.active:
                break
            await schedule.wait_one()
    except BaseException as exc:
        undelivered = await schedule.abandon()
        raise BatchInterrupted(exc, undelivered) from exc
    return schedule.hold_remaining()
