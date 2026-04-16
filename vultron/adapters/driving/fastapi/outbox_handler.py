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
(delivery failures are isolated per-recipient) from ``specs/outbox.md``.

OX-1.3 idempotency is enforced at the receiving inbox endpoint
(``POST /actors/{id}/inbox/``) rather than at delivery time, because actors
run as isolated processes with no direct access to each other's DataLayers.
"""

import logging
from typing import cast

from vultron.adapters.driven.delivery_queue import DeliveryQueueAdapter
from vultron.core.models.activity import VultronActivity
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.emitter import ActivityEmitter
from vultron.errors import VultronOutboxObjectIntegrityError
from vultron.wire.as2.vocab.base.links import as_Link

logger = logging.getLogger(__name__)


def _format_object(obj: object) -> str:
    """Return a concise one-line summary of an AS2 object for log messages.

    Produces ``<ClassName> <id>`` for Pydantic-like domain objects, passes
    strings through unchanged, and falls back to ``str(obj)`` otherwise.
    Handles ``None`` gracefully.

    Args:
        obj: The object to format — may be a domain model, a URI string, or
             ``None``.

    Returns:
        A short, human-readable representation of the object.
    """
    if obj is None:
        return "None"
    if isinstance(obj, str):
        return obj
    type_name = type(obj).__name__
    obj_id = getattr(obj, "id_", None)
    if obj_id is not None:
        return f"{type_name} {obj_id}"
    return type_name


def _extract_recipients(activity) -> list[str]:
    """Extract deduplicated recipient actor IDs from an AS2 activity.

    Reads the ``to``, ``cc``, ``bto``, and ``bcc`` addressing fields and
    returns a list of actor ID strings in the order first encountered.

    Args:
        activity: An AS2 activity with to/cc/bto/bcc attributes.

    Returns:
        Deduplicated list of recipient actor ID strings.
    """
    seen: set[str] = set()
    recipients: list[str] = []
    for field in ("to", "cc", "bto", "bcc"):
        val = getattr(activity, field, None)
        if val is None:
            continue
        items = val if isinstance(val, list) else [val]
        for item in items:
            if isinstance(item, str):
                actor_id = item
            elif hasattr(item, "id_"):
                actor_id = item.id_
            else:
                continue
            if actor_id not in seen:
                seen.add(actor_id)
                recipients.append(actor_id)
    return recipients


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

    activity = dl.read(activity_id)
    if activity is None:
        logger.warning(
            "Activity %s not found in DataLayer for actor %s; skipping"
            " delivery.",
            activity_id,
            actor_id,
        )
        return

    if isinstance(activity, VultronActivity):
        outbound_activity = activity
    elif hasattr(activity, "model_dump"):
        outbound_activity = VultronActivity.model_validate(
            activity.model_dump(by_alias=True)
        )
    else:
        logger.warning(
            "Activity %s could not be converted for delivery; skipping.",
            activity_id,
        )
        return

    activity_type = getattr(outbound_activity, "type_", "Activity")
    activity_object = getattr(outbound_activity, "object_", None)

    # For Create and Announce activities, expand an ID-string object_ to the
    # full domain object so the recipient inbox endpoint can store it separately
    # before dispatching.  For Create: the receiving side needs the full object
    # to recreate the case.  For Announce(CaseLogEntry): the receiving side
    # needs all CaseLogEntry fields for hash-chain validation (BUG-26041501;
    # a URI-only reference violates SYNC-02-004).
    #
    # NOTE: This expansion path is a backward-compatibility bridge for
    # activities stored before INLINE-OBJ-A narrowed object_ types.  New
    # outbound activities should always carry inline objects (MV-09-001).
    if activity_type in ("Create", "Announce") and isinstance(
        activity_object, str
    ):
        logger.warning(
            "Outbound %s activity '%s' has a bare string object_ '%s'."
            " Attempting DataLayer expansion (MV-09-001 violation).",
            activity_type,
            activity_id,
            activity_object,
        )
        full_obj = dl.read(activity_object)
        if full_obj is not None:
            outbound_activity.object_ = full_obj
            activity_object = full_obj
            logger.debug(
                "Expanded object_ from '%s' to full %s for %s"
                " activity '%s' delivery.",
                getattr(full_obj, "id_", activity_object),
                type(full_obj).__name__,
                activity_type,
                activity_id,
            )

    # Object integrity check: reject delivery of any outbound activity whose
    # object_ is still a bare string or an as_Link after the expansion attempt.
    # Outbound initiating activities must carry fully inline typed objects so
    # that recipients can determine the semantic type (MV-09-001, MV-09-002).
    if isinstance(activity_object, (str, as_Link)):
        raise VultronOutboxObjectIntegrityError(
            f"Outbound {activity_type} activity '{activity_id}' has an"
            f" inline object_ that is a bare string or Link"
            f" ({activity_object!r}). Outbound initiating activities must"
            " carry fully inline typed objects (MV-09-001).",
            activity_id=activity_id,
            activity_type=activity_type,
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
    shared_dl: DataLayer | None = None,
    emitter: ActivityEmitter | None = None,
) -> None:
    """Process the outbox for the given actor.

    Reads pending activity IDs from the actor-scoped DataLayer outbox queue
    and delivers each one to its addressed recipients via the
    ``ActivityEmitter`` port (OX-03-001).

    Delivery is performed by the emitter (HTTP POST for
    ``DeliveryQueueAdapter``) and does not block the HTTP response because
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
            ``DeliveryQueueAdapter()`` which delivers via HTTP POST.
    """
    _emitter = cast(
        ActivityEmitter,
        emitter if emitter is not None else DeliveryQueueAdapter(),
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
