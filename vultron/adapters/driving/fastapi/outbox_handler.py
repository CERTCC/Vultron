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

OX-1.3 idempotency is enforced at the receiving inbox endpoint
(``POST /actors/{id}/inbox/``) rather than at delivery time, because actors
run as isolated processes with no direct access to each other's DataLayers.

Helper concerns are split into focused sub-modules:

- ``outbox_addressing`` — recipient extraction and reference dehydration
- ``outbox_delivery`` — object validation, expansion, and preparation

All public and private symbols from those modules are re-exported here so
that callers using ``import outbox_handler as oh`` continue to resolve all
names (including those used by ``monkeypatch.setattr``) via this module's
namespace.
"""

import asyncio
import logging
import random
from typing import cast

from vultron.adapters.driven.http_delivery import (
    DeliveryError,
    HttpDeliveryAdapter,
)
from vultron.adapters.outbox_dead_letter import OutboxRetryStore

# ---------------------------------------------------------------------------
# Re-exports from outbox_addressing (keep in this namespace for compat)
# ---------------------------------------------------------------------------
from vultron.adapters.driving.fastapi.outbox_addressing import (  # noqa: F401
    _DEHYDRATION_FIELDS,
    _STUB_KEYS,
    _STUB_OBJECT_TYPES,
    _coerce_reference_value,
    _dehydrate_references,
    _extract_recipients,
    _format_object,
    _is_stub_object_dict,
)

# ---------------------------------------------------------------------------
# Re-exports from outbox_delivery (keep in this namespace for compat)
# ---------------------------------------------------------------------------
from vultron.adapters.driving.fastapi.outbox_delivery import (  # noqa: F401
    _INLINE_OBJECT_ACTIVITY_TYPES,
    _STUB_OBJECT_MODEL_MAP,
    _expand_inline_object,
    _hydrate_inline_object_if_persistable,
    _load_outbound_activity,
    _recover_typed_inline_object_from_dict,
    _validate_inline_object,
    _validate_to_field,
    _warn_secondary_addressing,
)
from vultron.core.models.activity import VultronActivity
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


def _prepare_activity_object_for_delivery(
    outbound_activity: VultronActivity,
    activity_id: str,
    activity_type: str,
    dl: DataLayer,
) -> object:
    """Normalize and validate ``object_`` before recipient delivery.

    Kept in this module (rather than ``outbox_delivery``) so that
    ``monkeypatch.setattr(oh, "_expand_inline_object", …)`` patches resolve
    correctly through this module's globals.
    """
    activity_object = getattr(outbound_activity, "object_", None)
    activity_object = _expand_inline_object(
        outbound_activity,
        activity_id,
        activity_type,
        activity_object,
        dl,
    )
    _validate_inline_object(activity_id, activity_type, activity_object)
    activity_object = _recover_typed_inline_object_from_dict(
        activity_object,
        activity_type,
        activity_id,
        outbound_activity,
    )
    return _hydrate_inline_object_if_persistable(
        activity_object, outbound_activity, dl
    )


async def handle_outbox_item(
    actor_id: str,
    activity_id: str,
    dl: DataLayer,
    emitter: ActivityEmitter,
) -> None:
    """Deliver a single outbox activity to its addressed recipients.

    Reads the activity from ``dl``, extracts recipient actor IDs from
    the ``to``, ``cc``, ``bto``, and ``bcc`` AS2 addressing fields, and
    calls ``await emitter.emit(activity, recipients)`` to deliver.

    Delivery failure for any one recipient is logged but does not abort
    delivery to other recipients (handled inside the emitter).

    Args:
        actor_id: The ID of the Actor whose outbox is being processed.
        activity_id: The ID of the activity to deliver.
        dl: The DataLayer to read the activity object from.
        emitter: The ActivityEmitter port implementation to use for delivery.
    """
    logger.info(
        "Processing outbox item for actor '%s': %s", actor_id, activity_id
    )

    outbound_activity = _load_outbound_activity(actor_id, activity_id, dl)
    if outbound_activity is None:
        return

    raw_activity_type = getattr(outbound_activity, "type_", "Activity")
    activity_type = (
        raw_activity_type if isinstance(raw_activity_type, str) else "Activity"
    )
    _validate_to_field(outbound_activity, activity_id, activity_type)
    _warn_secondary_addressing(outbound_activity, activity_id, activity_type)
    activity_object = _prepare_activity_object_for_delivery(
        outbound_activity, activity_id, activity_type, dl
    )

    recipients = _extract_recipients(outbound_activity)
    if not recipients:
        logger.debug(
            "No recipients found for %s activity '%s' (actor '%s').",
            activity_type,
            activity_id,
            actor_id,
        )
        return

    await emitter.emit(outbound_activity, recipients)
    logger.info(
        "Delivered %s activity '%s' (object: %s) to %d recipient(s)"
        " [%s] for actor '%s'.",
        activity_type,
        activity_id,
        _format_object(activity_object),
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

    OX-1.3 idempotency is enforced at the receiving inbox endpoint, not
    here (see ``routers/actors.py`` ``post_actor_inbox``).

    Args:
        actor_id: The ID of the Actor whose outbox is being processed.
        dl: The actor's DataLayer — outbox queue *and* the activity objects
            themselves.  Before ADR-0072 a separate ``shared_dl`` was used to
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
    _read_dl = dl

    # Resolve actor by full ID first, then fall back to short ID (mirrors
    # inbox_handler resolution so both handlers accept the same actor_id
    # forms).
    actor = _read_dl.read(actor_id)
    if actor is None:
        actor = _read_dl.find_actor_by_short_id(actor_id)
    if actor is None:
        logger.warning("Actor %s not found in outbox_handler.", actor_id)
        return

    logger.debug("Processing outbox for actor %s", actor_id)
    # dl satisfies OutboxRetryStore structurally (SqliteDataLayer implements
    # both); cast lets mypy/pyright see the delivery-infrastructure methods
    # without polluting the core DataLayer port with adapter concerns.  The
    # retry bookkeeping lands in this actor's own store (ADR-0072), so it needs
    # no actor argument.
    _retry: OutboxRetryStore = cast(OutboxRetryStore, dl)
    activity_err_counts: dict[str, int] = {}
    while dl.outbox_list():
        activity_id = dl.outbox_pop()
        if activity_id is None:
            break

        try:
            await handle_outbox_item(actor_id, activity_id, _read_dl, _emitter)
        except Exception as e:
            failed_recipients: list[str] = (
                list(e.failed_recipients)
                if isinstance(e, DeliveryError)
                else []
            )
            total = _retry.get_outbox_attempt_count(activity_id) + 1
            if total >= MAX_TOTAL_ATTEMPTS:
                # Budget exhausted — dead-letter the activity (OX-13-002).
                _retry.dead_letter_append(
                    activity_id,
                    reason="max_attempts_exhausted",
                    total_attempts=total,
                    failed_recipients=failed_recipients,
                )
                _retry.clear_outbox_attempt_count(activity_id)
                logger.error(
                    "Activity '%s' exhausted %d delivery attempts for actor"
                    " '%s'; moved to dead letter (OX-13-002)."
                    " Failed recipients: %s",
                    activity_id,
                    total,
                    actor_id,
                    failed_recipients,
                )
                # Do NOT re-queue — activity is permanently dead-lettered.
            else:
                _retry.set_outbox_attempt_count(activity_id, total)
                logger.error(
                    "Error processing outbox item '%s' (attempt %d): %s",
                    activity_id,
                    total,
                    e,
                )
                dl.outbox_append(activity_id)
                activity_err_counts[activity_id] = (
                    activity_err_counts.get(activity_id, 0) + 1
                )
                per_err = activity_err_counts[activity_id]
                if per_err > 3:
                    logger.error(
                        "Too many errors for outbox item '%s',"
                        " skipping for this pass (OX-13-006).",
                        activity_id,
                    )
                    # Stop when every remaining item has also hit its cap.
                    if all(
                        activity_err_counts.get(i, 0) > 3
                        for i in dl.outbox_list()
                    ):
                        break
                    continue
                # Back off before retrying to avoid hammering a busy recipient.
                backoff = (2 ** (per_err - 1)) + random.uniform(0, 0.5)
                await asyncio.sleep(backoff)
