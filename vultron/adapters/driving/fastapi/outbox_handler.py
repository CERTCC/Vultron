#!/usr/bin/env python

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""
Provides an outbox handler for Vultron Actors.

Implements OX-1.1 (local/remote delivery via HTTP POST), OX-1.2
(background delivery after inbox processing), and partial OX-1.3
(delivery failures are isolated per-recipient) from ``specs/outbox.yaml``.

One drain runs per actor outbox at a time (OX-01-004), and within a drain
rows are delivered in per-recipient lanes (OX-01-005, OX-01-006, ADR-0112;
see ``outbox_lanes.py``).  Every inbound activity's background task and the
``OutboxMonitor`` call :func:`outbox_handler`; before ADR-0112 those calls
drained one FIFO concurrently and a recipient could see rows complete in any
order, which is what turned a ledger fan-out into a Reject/replay storm
(#3602, #3033, #2898).

OX-1.3 idempotency is enforced at the receiving inbox endpoint
(``POST /actors/{id}/inbox/``) rather than at delivery time, because actors
run as isolated processes with no direct access to each other's DataLayers.

The handler is a dumb relay (VM-08-003, ADR-0074): each row's *sealed body*
— the JSON text the emitting adapter produced and stored alongside the
activity — is delivered exactly as sealed.  Nothing here reads the activity
record back, expands a reference, hydrates an object, or re-serialises.  That
is what keeps the ledger's ``payloadSnapshot`` and the wire identical.

Helper concerns are split into focused sub-modules:

- ``outbox_addressing`` — recipient extraction from the parsed body
- ``outbox_delivery`` — sealed-body loading and last-resort guards

Tests that stub the handler do so via ``import outbox_handler as oh`` and
``monkeypatch.setattr(oh, "handle_outbox_item", …)``; the helpers themselves
are imported from their own modules.
"""

import asyncio
import logging
import random
from typing import cast

from vultron.adapters.driven.http_delivery import (
    DeliveryError,
    HttpDeliveryAdapter,
)
from vultron.adapters.driving.fastapi.outbox_lanes import (
    BatchInterrupted,
    RowOutcome,
    StallOrder,
    deliver_batch,
    lane_keys,
)
from vultron.adapters.outbox_dead_letter import OutboxRetryStore

# ---------------------------------------------------------------------------
# Re-exports from outbox_addressing (keep in this namespace for compat)
# ---------------------------------------------------------------------------
from vultron.adapters.driving.fastapi.outbox_addressing import (
    _extract_recipients,
    _format_object,
)
from vultron.adapters.driving.fastapi.outbox_delivery import (
    _activity_type,
    _load_sealed_body,
    _validate_inline_object,
    _validate_to_field,
    _warn_secondary_addressing,
)
from vultron.adapters.outbox_sealed_body import (
    parse_sealed_body,
    read_sealed_body_dict,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.emitter import ActivityEmitter

logger = logging.getLogger(__name__)

#: Maximum cumulative delivery attempts across all drain passes before an
#: activity is moved to the dead-letter store (OX-13-002).  Chosen as
#: (DEFAULT_MAX_RETRIES + 1) × ~3 drain passes — survives transient failures
#: without running indefinitely.  See ADR-0066.
MAX_TOTAL_ATTEMPTS: int = 12

# ---------------------------------------------------------------------------
# Default emitter singleton
# ---------------------------------------------------------------------------
# Set via ``configure_default_emitter()`` during app startup so the
# HttpDeliveryAdapter is the module-level default for all outbox drains.
# Falls back to a fresh ``HttpDeliveryAdapter`` when not configured.
_default_emitter: ActivityEmitter | None = None


def _resolve_ledger_entry_id(activity_id: str, dl: DataLayer) -> str | None:
    """Return the CaseLedgerEntry ID if *activity_id* is an Announce(CaseLedgerEntry).

    Reads the sealed body and extracts ``object.id`` when the inline object's
    type is ``"CaseLedgerEntry"``.  Returns ``None`` for all other activity
    types so non-ledger activities dead-letter unchanged (OX-14-001).

    The CaseLedgerEntry is always committed before its fan-out activity is
    queued (emit-after-commit invariant, OX-14-002), so the entry is always
    present when this function runs.
    """
    try:
        body = read_sealed_body_dict(dl, activity_id)
    except Exception:
        return None
    if body is None:
        return None
    obj = body.get("object")
    if not isinstance(obj, dict) or obj.get("type") != "CaseLedgerEntry":
        return None
    entry_id = obj.get("id")
    return entry_id if isinstance(entry_id, str) else None


def configure_default_emitter(emitter: ActivityEmitter) -> None:
    """Set the default ``ActivityEmitter`` for ``outbox_handler``.

    Called once during app lifespan to install the ``HttpDeliveryAdapter``
    (ADR-0042) so all inter-actor deliveries use the uniform HTTP path.
    """
    global _default_emitter  # noqa: PLW0603
    _default_emitter = emitter


def get_default_emitter() -> ActivityEmitter:
    """Return the configured default emitter, or a fresh ``HttpDeliveryAdapter``."""
    return _default_emitter or HttpDeliveryAdapter()


async def handle_outbox_item(
    actor_id: str,
    activity_id: str,
    dl: DataLayer,
    emitter: ActivityEmitter,
) -> None:
    """Deliver a single outbox activity to its addressed recipients.

    Reads the activity's sealed body from ``dl``, applies the last-resort
    guards (``to:`` present, inline ``object``), extracts recipient actor IDs
    from the ``to``, ``cc``, ``bto``, and ``bcc`` addressing fields, and calls
    ``await emitter.emit(activity_id, body, recipients)`` to deliver the body
    exactly as sealed (VM-08-003).

    Delivery failure for any one recipient is logged but does not abort
    delivery to other recipients (handled inside the emitter).

    Args:
        actor_id: The ID of the Actor whose outbox is being processed.
        activity_id: The ID of the activity to deliver.
        dl: The DataLayer to read the sealed body from.
        emitter: The ActivityEmitter port implementation to use for delivery.
    """
    logger.info(
        "Processing outbox item for actor '%s': %s", actor_id, activity_id
    )

    sealed = _load_sealed_body(actor_id, activity_id, dl)
    if sealed is None:
        return
    body = parse_sealed_body(sealed)

    activity_type = _activity_type(body)
    _validate_to_field(body, activity_id, activity_type)
    _warn_secondary_addressing(body, activity_id, activity_type)
    _validate_inline_object(body, activity_id, activity_type)

    # ``to:`` has just been checked to name someone, so this is non-empty.
    recipients = _extract_recipients(body)
    await emitter.emit(activity_id, sealed.body, recipients)
    logger.info(
        "Delivered %s activity '%s' (object: %s) to %d recipient(s)"
        " [%s] for actor '%s'.",
        activity_type,
        activity_id,
        _format_object(body.get("object")),
        len(recipients),
        ", ".join(recipients),
        actor_id,
    )


async def outbox_handler(
    actor_id: str,
    dl: DataLayer,
    emitter: ActivityEmitter | None = None,
) -> None:
    """Process the outbox for the given actor.

    Reads pending activity IDs from the actor-scoped DataLayer outbox queue
    and delivers each one to its addressed recipients via the
    ``ActivityEmitter`` port (OX-03-001).

    Delivery is performed by the emitter (HTTP POST for
    ``HttpDeliveryAdapter``) and does not block the HTTP response because
    this coroutine is scheduled as a FastAPI BackgroundTask (OX-03-003).

    Only one drain of *actor_id*'s outbox runs at a time (OX-01-004): a call
    made while another is draining asks that drain to look at the queue
    once more before it finishes, and returns.  Within the drain, rows are
    scheduled in per-recipient lanes — see :mod:`outbox_lanes` (ADR-0112).

    OX-1.3 idempotency is enforced at the receiving inbox endpoint, not
    here (see ``routers/actors.py`` ``post_actor_inbox``).

    Args:
        actor_id: The ID of the Actor whose outbox is being processed.
        dl: The actor's DataLayer — outbox queue *and* the activity objects
            themselves.  Before ADR-0073 a separate ``shared_dl`` was used to
            read the activities, which only worked because the shared pool saw
            every actor's rows; the activity an actor queued is its own data
            and lives in its own store.
        emitter: The ActivityEmitter port to use for delivery. Defaults to
            the configured emitter (``HttpDeliveryAdapter`` by default,
            ADR-0042).
    """
    _emitter = cast(
        ActivityEmitter,
        emitter if emitter is not None else get_default_emitter(),
    )

    # Resolve actor by full ID first, then fall back to short ID (mirrors
    # inbox_handler resolution so both handlers accept the same actor_id
    # forms).
    actor = dl.read(actor_id)
    if actor is None:
        actor = dl.find_actor_by_short_id(actor_id)
    if actor is None:
        logger.warning("Actor %s not found in outbox_handler.", actor_id)
        return

    logger.debug("Processing outbox for actor %s", actor_id)
    # Key the slot on the *store's* identity, not the id the caller typed: a
    # trigger route forwards the URL segment (a short id) while the inbox path
    # and `_emitting_outbox` pass the canonical URI, and both name one outbox.
    slot_key = getattr(actor, "id_", None) or actor_id
    slot = _drain_slot(slot_key)
    if slot.busy:
        # Another drain of this outbox is running (OX-01-004).  It sees every
        # row already queued on its next look; asking it to look once more
        # after it believes it is done closes the window between its last
        # look and its release, so nothing is left for the safety-net poll.
        # Waiting instead would deadlock a *nested* call: under Starlette's
        # TestClient a recipient's BackgroundTask runs inside the sender's
        # POST, so a loopback or round-trip delivery re-enters this function
        # for the same actor while the outer drain is awaiting that very POST.
        # Production uvicorn answers 202 before the task runs and never
        # nests, but a drain policy must not have a deadlock class at all.
        slot.rerun = True
        logger.debug(
            "Outbox for actor %s is already being drained; the running drain"
            " will look again before it finishes.",
            actor_id,
        )
        return
    slot.busy = True
    try:
        await _drain_outbox(actor_id, dl, _emitter, slot)
    finally:
        slot.busy = False


class _DrainSlot:
    """One actor's drain state (OX-01-004).

    ``busy`` is set for the whole drain — it is a flag, not a lock, because
    no caller ever waits on it; ``rerun`` is set by a caller that found the
    drain running and means "look at the queue once more before you finish".
    """

    __slots__ = ("busy", "rerun")

    def __init__(self) -> None:
        self.busy = False
        self.rerun = False


_drain_slots: dict[str, _DrainSlot] = {}


def _drain_slot(actor_id: str) -> _DrainSlot:
    """Return the drain slot for *actor_id* (the store's canonical id)."""
    slot = _drain_slots.get(actor_id)
    if slot is None:
        slot = _drain_slots[actor_id] = _DrainSlot()
    return slot


async def _drain_outbox(
    actor_id: str,
    dl: DataLayer,
    emitter: ActivityEmitter,
    slot: _DrainSlot,
) -> None:
    """One drain pass: pop the queue in batches and deliver each in lanes.

    Runs while the actor's drain slot is busy.  A batch is the queue as it
    stood when the pass looked; rows appended while a batch is in flight form
    the next one.  The pass ends when the queue is empty or holds only rows
    stalled in this pass (OX-13-011) — and no other caller has asked for one
    more look (``slot.rerun``) — leaving stalled rows in enqueue order for the
    next drain (OX-13-012).

    A batch is held in memory while it is delivered — the rows in flight, and
    the rows waiting behind them in a busy lane.  If the batch is interrupted
    (an unexpected error, or the ``OutboxMonitor`` canceling this task at
    shutdown) every row that was not delivered or dead-lettered is appended
    back to the queue before the error propagates, so the failure costs the
    pass, not the rows.  A hard process crash mid-batch loses what was popped
    — the same class of loss ADR-0066 accepted for the one in-flight row,
    widened to the batch (ADR-0112).
    """
    # dl satisfies OutboxRetryStore structurally (SqliteDataLayer implements
    # both); cast lets mypy/pyright see the delivery-infrastructure methods
    # without polluting the core DataLayer port with adapter concerns.  The
    # retry bookkeeping lands in this actor's own store (ADR-0073), so it needs
    # no actor argument.
    retry: OutboxRetryStore = cast(OutboxRetryStore, dl)
    err_counts: dict[str, int] = {}
    stalled = StallOrder()

    async def deliver(activity_id: str) -> RowOutcome:
        return await _deliver_row(
            actor_id, activity_id, dl, emitter, retry, err_counts
        )

    while True:
        pending = dl.outbox_list()
        if not pending or stalled.covers(pending):
            if not slot.rerun:
                break
            slot.rerun = False
            continue
        rows: list[tuple[str, frozenset[str]]] = []
        for _ in pending:
            activity_id = dl.outbox_pop()
            if activity_id is None:
                break
            rows.append((activity_id, lane_keys(activity_id, dl)))
        try:
            requeue = await deliver_batch(rows, deliver, stalled)
        except BatchInterrupted as exc:
            _requeue_after_interruption(actor_id, dl, exc)
            raise
        for activity_id in requeue:
            dl.outbox_append(activity_id)


def _requeue_after_interruption(
    actor_id: str, dl: DataLayer, exc: BatchInterrupted
) -> None:
    """Put an interrupted batch's undelivered rows back, then let it propagate.

    A cancellation (or any other ``BaseException``) is re-raised as itself so
    that the ``OutboxMonitor``'s task actually stops; an ordinary error
    propagates as the :class:`BatchInterrupted` that carries it.
    """
    logger.error(
        "Outbox drain for actor '%s' interrupted (%s); re-queueing"
        " %d undelivered row(s)",
        actor_id,
        exc,
        len(exc.undelivered),
    )
    for activity_id in exc.undelivered:
        dl.outbox_append(activity_id)
    if not isinstance(exc.cause, Exception):
        raise exc.cause from None


async def _deliver_row(
    actor_id: str,
    activity_id: str,
    dl: DataLayer,
    emitter: ActivityEmitter,
    retry: OutboxRetryStore,
    err_counts: dict[str, int],
) -> RowOutcome:
    """Deliver one row, retrying in-pass with backoff up to the per-pass cap.

    Every failure increments the persisted total attempt count (OX-13-001);
    exhausting it dead-letters the row (OX-13-002/003/009).  Below that, up
    to three in-pass retries back off exponentially; a fourth failure stalls
    the row for this pass (OX-13-006, OX-13-010, OX-13-011).
    """
    while True:
        try:
            await handle_outbox_item(actor_id, activity_id, dl, emitter)
            return RowOutcome.DELIVERED
        except Exception as e:  # noqa: BLE001 — every failure is bookkept
            try:
                return_now = _bookkeep_failure(
                    actor_id, activity_id, dl, retry, err_counts, e
                )
            except Exception as bookkeeping_error:  # noqa: BLE001
                # The retry store itself failed.  The row is not lost — the
                # caller re-queues a stalled row — but nothing more can be
                # learned about it this pass (OX-13-011).
                logger.error(
                    "Outbox retry bookkeeping failed for '%s' (actor '%s'):"
                    " %s; stalling the row for this pass",
                    activity_id,
                    actor_id,
                    bookkeeping_error,
                )
                return RowOutcome.STALLED
            if return_now is not None:
                return return_now
            per_err = err_counts[activity_id]
            # Back off before retrying to avoid hammering a busy recipient.
            backoff = (2 ** (per_err - 1)) + random.uniform(0, 0.5)
            await asyncio.sleep(backoff)


def _bookkeep_failure(
    actor_id: str,
    activity_id: str,
    dl: DataLayer,
    retry: OutboxRetryStore,
    err_counts: dict[str, int],
    e: Exception,
) -> RowOutcome | None:
    """Record one failed attempt; return the row's outcome or ``None`` to retry."""
    failed_recipients: list[str] = (
        list(e.failed_recipients) if isinstance(e, DeliveryError) else []
    )
    total = retry.get_outbox_attempt_count(activity_id) + 1
    if total >= MAX_TOTAL_ATTEMPTS:
        _dead_letter(
            actor_id, activity_id, dl, retry, total, failed_recipients
        )
        return RowOutcome.DEAD_LETTERED
    retry.set_outbox_attempt_count(activity_id, total)
    logger.error(
        "Error processing outbox item '%s' (attempt %d): %s",
        activity_id,
        total,
        e,
    )
    per_err = err_counts[activity_id] = err_counts.get(activity_id, 0) + 1
    if per_err > 3:
        logger.error(
            "Too many errors for outbox item '%s',"
            " skipping for this pass (OX-13-006).",
            activity_id,
        )
        return RowOutcome.STALLED
    return None


def _dead_letter(
    actor_id: str,
    activity_id: str,
    dl: DataLayer,
    retry: OutboxRetryStore,
    total: int,
    failed_recipients: list[str],
) -> None:
    """Budget exhausted — dead-letter the activity (OX-13-002), never re-queue."""
    # Resolve the ledger entry being replicated, if any (OX-14-001).
    ledger_entry_id = _resolve_ledger_entry_id(activity_id, dl)
    retry.dead_letter_append(
        activity_id,
        reason="max_attempts_exhausted",
        total_attempts=total,
        failed_recipients=failed_recipients,
        ledger_entry_id=ledger_entry_id,
    )
    retry.clear_outbox_attempt_count(activity_id)
    logger.error(
        "Activity '%s' exhausted %d delivery attempts for actor"
        " '%s'; moved to dead letter (OX-13-002)."
        " Failed recipients: %s",
        activity_id,
        total,
        actor_id,
        failed_recipients,
    )
