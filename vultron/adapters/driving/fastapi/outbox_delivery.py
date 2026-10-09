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
Sealed-body loading and last-resort guards for outbox delivery.

The outbox handler is a dumb relay (VM-08-003, ADR-0074): it delivers the
body the emitting adapter sealed, and it never expands, hydrates, or re-types
what it delivers.  These helpers load that body and apply the guards that
refuse a body rather than repair it:

- Sealed-body loading (:func:`_load_sealed_body`)
- ``to:`` field enforcement (OX-08-001, OX-08-002)
- ``cc``/``bto``/``bcc`` secondary-addressing warnings (OX-08-004)
- Inline ``object`` integrity as a last-resort guard (AKM-03-002, MV-09-002)

Every helper reads the parsed body ``dict``.  There is no activity object on
this path any more: the record the DataLayer holds is a dehydrated,
rehydrated-on-read reconstruction, and delivering it is what made the ledger's
``payloadSnapshot`` and the wire disagree (#2655).
"""

import logging
from typing import Any

from vultron.adapters.driving.fastapi.outbox_addressing import (
    _item_actor_id,
)
from vultron.adapters.outbox_sealed_body import (
    SealedOutboundBody,
    read_sealed_body,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.errors import (
    VultronOutboxObjectIntegrityError,
    VultronOutboxToFieldMissingError,
)

logger = logging.getLogger(__name__)

#: Activity types whose ``object`` MUST be a fully inline typed object
#: (AKM-03-001).  ``Accept`` is held to the same standard because every
#: Vultron ``Accept`` embeds the activity it answers (#2194).
_INLINE_OBJECT_ACTIVITY_TYPES: frozenset[str] = frozenset(
    {
        "Create",
        "Offer",
        "Invite",
        "Announce",
        "Add",
        "Remove",
        "Update",
        "Join",
        "Ignore",
        "Leave",
        "Accept",
    }
)


def _load_sealed_body(
    actor_id: str,
    activity_id: str,
    dl: DataLayer,
) -> SealedOutboundBody | None:
    """Return the sealed body of *activity_id* from *dl*, or ``None``.

    A queued id with no sealed body has nothing to deliver.  That is a defect
    in whoever queued it — every adapter that persists an outbound activity
    seals it — so it is reported at ERROR and the row is dropped, the way a
    missing activity record always was.
    """
    sealed = read_sealed_body(dl, activity_id)
    if sealed is None:
        logger.error(
            "No sealed body for outbox row '%s' of actor '%s'; nothing to"
            " deliver, dropping the row (VM-08-003).",
            activity_id,
            actor_id,
        )
        return None
    return sealed


def _activity_type(body: dict[str, Any]) -> str:
    """Return the body's ``type``, or ``"Activity"`` when it names none."""
    raw = body.get("type")
    return raw if isinstance(raw, str) and raw else "Activity"


def _validate_to_field(
    body: dict[str, Any],
    activity_id: str,
    activity_type: str,
) -> None:
    """Refuse a body whose ``to:`` names no recipient (OX-08-001/002/003).

    Absent, empty, and present-but-unusable (``[""]``, an object without an
    ``id``) are the same defect: nothing would be delivered.  Refusing all
    three here keeps the row from being silently consumed later.
    """
    to_field = body.get("to")
    items = to_field if isinstance(to_field, list) else [to_field]
    if not any(_item_actor_id(item) for item in items):
        raise VultronOutboxToFieldMissingError(
            f"Outbound {activity_type} activity '{activity_id}' has no"
            " `to:` field, or its `to:` names no recipient. All outbound"
            " Vultron activities MUST address at least one recipient via"
            " `to:` (OX-08-001).",
            activity_id=activity_id,
            activity_type=activity_type,
        )


def _warn_secondary_addressing(
    body: dict[str, Any],
    activity_id: str,
    activity_type: str,
) -> None:
    # No exemption, not even for the sender's own id in ``cc:`` (OX-08-004):
    # the CLP-10-001 self-copy was retired by ADR-0109, so a sender copying
    # itself is exactly what the warning exists to surface.
    for addr_field in ("cc", "bto", "bcc"):
        value = body.get(addr_field)
        if value is None or value == []:
            continue
        logger.warning(
            "Outbound %s activity '%s' has `%s:` set."
            " Vultron direct messages should only use `to:` for"
            " addressing (OX-08-004).",
            activity_type,
            activity_id,
            addr_field,
        )


def _is_link(value: object) -> bool:
    """True for an AS2 ``Link`` object: ``{"type": "Link", ...}`` or ``href``."""
    return isinstance(value, dict) and (
        value.get("type") == "Link" or "href" in value
    )


def _validate_inline_object(
    body: dict[str, Any],
    activity_id: str,
    activity_type: str,
) -> None:
    """Refuse a body whose ``object`` is a reference (AKM-03-002, MV-09-002).

    This is the last-resort guard.  Nothing is expanded here: an ``object``
    the factory left as a bare URI or a ``Link`` is a factory defect, and the
    recipient — which has no access to this actor's store — could not resolve
    it either.
    """
    if activity_type not in _INLINE_OBJECT_ACTIVITY_TYPES:
        return
    activity_object = body.get("object")
    if isinstance(activity_object, str) or _is_link(activity_object):
        raise VultronOutboxObjectIntegrityError(
            f"Outbound {activity_type} activity '{activity_id}' has an"
            f" inline object that is a bare string or Link"
            f" ({activity_object!r}). Outbound initiating activities must"
            " carry fully inline typed objects (AKM-03-001).",
            activity_id=activity_id,
            activity_type=activity_type,
        )
