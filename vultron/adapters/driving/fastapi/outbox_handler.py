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

from vultron.adapters.driven.delivery_queue import DeliveryQueueAdapter
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.emitter import ActivityEmitter

logger = logging.getLogger(__name__)


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
            elif hasattr(item, "as_id"):
                actor_id = item.as_id
            else:
                continue
            if actor_id not in seen:
                seen.add(actor_id)
                recipients.append(actor_id)
    return recipients


def handle_outbox_item(
    actor_id: str,
    activity_id: str,
    dl: DataLayer,
    emitter: ActivityEmitter,
) -> None:
    """Deliver a single outbox activity to its addressed recipients.

    Reads the activity from ``dl``, extracts recipient actor IDs from
    the ``to``, ``cc``, ``bto``, and ``bcc`` AS2 addressing fields, and
    calls ``emitter.emit(activity, recipients)`` to deliver.

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
            "Activity %s not found in DataLayer for actor %s; skipping delivery.",
            activity_id,
            actor_id,
        )
        return

    recipients = _extract_recipients(activity)
    if not recipients:
        logger.debug(
            "No recipients found for activity %s (actor %s).",
            activity_id,
            actor_id,
        )
        return

    emitter.emit(activity, recipients)
    logger.info(
        "Emitted activity %s to %d recipient(s) for actor %s.",
        activity_id,
        len(recipients),
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
        shared_dl: The shared DataLayer for reading activity objects.
            Defaults to ``dl`` when ``None`` (covers the ``POST /outbox``
            case where activities are stored in the actor's own DL).
        emitter: The ActivityEmitter port to use for delivery. Defaults to
            ``DeliveryQueueAdapter()`` which delivers via HTTP POST.
    """
    _emitter = emitter if emitter is not None else DeliveryQueueAdapter()
    _read_dl = shared_dl if shared_dl is not None else dl

    actor = _read_dl.read(actor_id)
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
            handle_outbox_item(actor_id, activity_id, _read_dl, _emitter)
        except Exception as e:
            logger.error(
                "Error processing outbox item for actor %s: %s", actor_id, e
            )
            dl.outbox_append(activity_id)
            err_count += 1
            if err_count > 3:
                logger.error(
                    "Too many errors processing outbox for actor %s, aborting.",
                    actor_id,
                )
                break
