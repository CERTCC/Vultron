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

import logging
from typing import cast

from vultron.adapters.driven.demo_http_delivery import DemoHttpDeliveryAdapter

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
from vultron.core.ports.datalayer import ActorScopedDataLayer, DataLayer
from vultron.core.ports.emitter import ActivityEmitter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default emitter singleton
# ---------------------------------------------------------------------------
# Set via ``configure_default_emitter()`` during app startup so all
# ``outbox_handler`` calls use local ASGI delivery for co-located actors.
# Falls back to ``DemoHttpDeliveryAdapter`` (HTTP-only) when not configured.
_default_emitter: ActivityEmitter | None = None


def configure_default_emitter(emitter: ActivityEmitter) -> None:
    """Set the default ``ActivityEmitter`` for ``outbox_handler``.

    Called once during app lifespan to install the ``ASGIEmitter`` so
    co-located actors (e.g. Case Actor) receive messages through the
    normal inbox pipeline rather than failing silently on HTTP delivery.
    """
    global _default_emitter  # noqa: PLW0603
    _default_emitter = emitter


def get_default_emitter() -> ActivityEmitter:
    """Return the configured default emitter, or ``DemoHttpDeliveryAdapter``."""
    return _default_emitter or DemoHttpDeliveryAdapter()


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
    dl: ActorScopedDataLayer,
    shared_dl: DataLayer | None = None,
    emitter: ActivityEmitter | None = None,
) -> None:
    """Process the outbox for the given actor.

    Reads pending activity IDs from the actor-scoped DataLayer outbox queue
    and delivers each one to its addressed recipients via the
    ``ActivityEmitter`` port (OX-03-001).

    Delivery is performed by the emitter (HTTP POST for
    ``DemoHttpDeliveryAdapter``) and does not block the HTTP response because
    this coroutine is scheduled as a FastAPI BackgroundTask (OX-03-003).

    OX-1.3 idempotency is enforced at the receiving inbox endpoint, not
    here (see ``routers/actors.py`` ``post_actor_inbox``).

    Args:
        actor_id: The ID of the Actor whose outbox is being processed.
        dl: The actor-scoped DataLayer (outbox queue management).
        shared_dl: The shared DataLayer for reading activity objects and
            resolving the actor.  Defaults to ``dl`` when ``None`` (covers
            the ``POST /outbox`` case where activities are stored in the
            actor's own DL).
        emitter: The ActivityEmitter port to use for delivery. Defaults to
            the configured emitter (``ASGIEmitter`` when available, otherwise
            ``DemoHttpDeliveryAdapter``).
    """
    _emitter = cast(
        ActivityEmitter,
        emitter if emitter is not None else get_default_emitter(),
    )
    _read_dl = shared_dl if shared_dl is not None else dl

    # Resolve actor by full ID first, then fall back to short ID (mirrors
    # inbox_handler resolution so both handlers accept the same actor_id
    # forms).
    actor = _read_dl.read(actor_id)
    if actor is None:
        actor = _read_dl.find_actor_by_short_id(actor_id)
    if actor is None:
        logger.warning("Actor %s not found in outbox_handler.", actor_id)
        return

    logger.info("Processing outbox for actor %s", actor_id)
    err_count = 0
    while dl.outbox_list():
        activity_id = dl.outbox_pop()
        if activity_id is None:
            break

        try:
            await handle_outbox_item(actor_id, activity_id, _read_dl, _emitter)
        except Exception as e:
            logger.error(
                "Error processing outbox item for actor %s: %s", actor_id, e
            )
            dl.outbox_append(activity_id)
            err_count += 1
            if err_count > 3:
                logger.error(
                    "Too many errors processing outbox for actor %s,"
                    " aborting.",
                    actor_id,
                )
                break
