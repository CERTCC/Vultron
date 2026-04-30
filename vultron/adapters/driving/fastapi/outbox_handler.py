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
"""

import logging
from typing import cast

from vultron.adapters.driven.delivery_queue import DeliveryQueueAdapter
from vultron.core.models.activity import VultronActivity
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.emitter import ActivityEmitter
from vultron.errors import (
    VultronOutboxObjectIntegrityError,
    VultronOutboxToFieldMissingError,
)
from vultron.wire.as2.vocab.base.links import as_Link

logger = logging.getLogger(__name__)

# Reference fields that must be collapsed to URI strings before validating as
# VultronActivity.  ``object`` is intentionally excluded — it must remain a
# full inline typed object so recipients can determine the semantic type
# (MV-09-001).
#
# ``target`` is also partially excluded: minimal stub dicts
# ``{id, type[, summary]}`` are preserved so that ``Invite.target`` carries
# the case type to the recipient (MV-10-001).
_DEHYDRATION_FIELDS: frozenset[str] = frozenset(
    {
        "actor",
        "target",
        "to",
        "cc",
        "bto",
        "bcc",
        "origin",
        "result",
        "instrument",
    }
)

# Keys permitted in a stub dict (MV-10-001).  Any other key causes full
# dehydration to a bare URI so that only intentional stubs are preserved.
_STUB_KEYS: frozenset[str] = frozenset({"id", "type", "summary", "@context"})

# AS2 object types that are intentional stubs and must be preserved in-line
# rather than collapsed to a bare URI string.
_STUB_OBJECT_TYPES: frozenset[str] = frozenset({"VulnerabilityCase"})


def _dehydrate_references(activity_dict: dict) -> dict:
    """Collapse domain-object dicts in reference fields to URI strings.

    Adapts a raw ``model_dump(by_alias=True)`` dict for ``VultronActivity``
    validation.  Wire-layer AS2 activities may carry full domain objects
    (e.g. ``VulnerabilityCase``) in reference fields such as ``target``.
    ``VultronActivity`` expects those fields to be URI strings, so this
    function collapses any dict with ``"href"`` or ``"id"`` to the
    corresponding URI string.  List fields are handled element-wise.

    ``"object"`` is explicitly excluded from dehydration because outbound
    initiating activities must carry a fully inline typed object for semantic
    routing on the receiving side (MV-09-001).

    Args:
        activity_dict: Raw ``dict`` produced by ``model_dump(by_alias=True)``
            on a typed AS2 activity model.

    Returns:
        A new ``dict`` with reference fields collapsed to URI strings where
        possible.
    """

    def _coerce(value: object) -> object:
        if not isinstance(value, dict):
            return value
        # Preserve minimal stub dicts that carry {id, type} for selective
        # disclosure (MV-10-001).  Only VulnerabilityCase stubs are preserved;
        # all other object dicts (e.g. actors) are collapsed to a bare URI.
        if (
            value.get("type") in _STUB_OBJECT_TYPES
            and value.keys() <= _STUB_KEYS
        ):
            return value
        # Prefer href (AS2 Link) then id (any AS2 object)
        uri = value.get("href") or value.get("id")
        return uri if uri is not None else value

    result = dict(activity_dict)
    for field in _DEHYDRATION_FIELDS:
        value = result.get(field)
        if value is None:
            continue
        if isinstance(value, list):
            result[field] = [_coerce(item) for item in value]
        else:
            result[field] = _coerce(value)
    return result


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
        raw = _dehydrate_references(
            activity.model_dump(by_alias=True, serialize_as_any=True)
        )
        outbound_activity = VultronActivity.model_validate(raw)
    else:
        logger.warning(
            "Activity %s could not be converted for delivery; skipping.",
            activity_id,
        )
        return

    activity_type = getattr(outbound_activity, "type_", "Activity")
    activity_object = getattr(outbound_activity, "object_", None)

    # Validate to: field (OX-08-001, OX-08-002, OX-08-003)
    to_field = getattr(outbound_activity, "to", None)
    _to_empty = to_field is None or (
        isinstance(to_field, list) and len(to_field) == 0
    )
    if _to_empty:
        raise VultronOutboxToFieldMissingError(
            f"Outbound {activity_type} activity '{activity_id}' has no"
            " `to:` field. All outbound Vultron activities MUST address"
            " at least one recipient via `to:` (OX-08-001).",
            activity_id=activity_id,
            activity_type=activity_type,
        )

    # Warn if cc/bto/bcc are set (OX-08-004)
    for _addr_field in ("cc", "bto", "bcc"):
        _val = getattr(outbound_activity, _addr_field, None)
        if _val is not None and _val != []:
            logger.warning(
                "Outbound %s activity '%s' has `%s:` set."
                " Vultron direct messages should only use `to:` for"
                " addressing (OX-08-004).",
                activity_type,
                activity_id,
                _addr_field,
            )

    # For initiating activity types, expand an ID-string object_ to the full
    # domain object so the recipient inbox endpoint can store it separately
    # before dispatching.  For Create: the receiving side needs the full object
    # to recreate the case.  For Announce(CaseLogEntry): the receiving side
    # needs all CaseLogEntry fields for hash-chain validation (BUG-26041501;
    # a URI-only reference violates SYNC-02-004).  For Add, Invite, Accept:
    # the receiving side needs the full inline object to determine semantic
    # type and update its own state correctly.
    #
    # NOTE: This expansion path is a backward-compatibility bridge for
    # activities stored before INLINE-OBJ-A narrowed object_ types.  New
    # outbound activities should always carry inline objects (MV-09-001).
    #
    # TODO: When "Join" and "Remove" are implemented they will also require
    # expansion here.
    if activity_type in (
        "Create",
        "Announce",
        "Add",
        "Invite",
        "Accept",
    ) and isinstance(activity_object, str):
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
