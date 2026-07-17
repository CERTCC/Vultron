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
Object validation and preparation helpers for outbox delivery.

Provides helpers that load, validate, and normalise outbound AS2 activities
before per-recipient delivery:

- Activity loading from the DataLayer with dehydration fallback
- ``to:`` field enforcement (OX-08-001, OX-08-002)
- ``cc``/``bto``/``bcc`` secondary-addressing warnings (OX-08-004)
- Bare-string ``object_`` expansion for initiating activity types (MV-09-001)
- Inline ``object_`` integrity validation
- Dict-based object recovery and DataLayer hydration
"""

import logging

from pydantic import BaseModel

from vultron.adapters.driving.fastapi.outbox_addressing import (
    _STUB_KEYS,
    _dehydrate_references,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import DataLayer
from vultron.errors import (
    VultronOutboxObjectIntegrityError,
    VultronOutboxToFieldMissingError,
)
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.objects.case_ledger_entry import as_CaseLedgerEntry
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

# Maps AS2 type strings to their wire-layer model classes for dict recovery.
# Used in _recover_typed_inline_object_from_dict to reconstruct typed models
# from plain dicts that result from the model_dump() → VultronActivity
# .model_validate() round-trip.  CaseLedgerEntry is included so an outbound
# Announce(CaseLedgerEntry) re-types its inline entry (whose fields survive
# because VultronActivity.object_ is ``Any``) before wire serialization,
# keeping the full inline entry on the wire (SYNC-02-004, SYNC-13-004).
_STUB_OBJECT_MODEL_MAP: dict[str, type[BaseModel]] = {
    "CaseProposal": as_CaseProposal,
    "VulnerabilityCase": as_VulnerabilityCase,
    "CaseLedgerEntry": as_CaseLedgerEntry,
}

_INLINE_OBJECT_ACTIVITY_TYPES: frozenset[str] = frozenset(
    {"Create", "Announce", "Add", "Invite", "Accept", "Offer", "Join"}
)


def _load_outbound_activity(
    actor_id: str,
    activity_id: str,
    dl: DataLayer,
) -> VultronActivity | None:
    activity = dl.read(activity_id)
    if activity is None:
        logger.warning(
            "Activity %s not found in DataLayer for actor %s; skipping"
            " delivery.",
            activity_id,
            actor_id,
        )
        return None

    if isinstance(activity, VultronActivity):
        return activity
    if hasattr(activity, "model_dump"):
        raw = _dehydrate_references(
            activity.model_dump(by_alias=True, serialize_as_any=True)
        )
        return VultronActivity.model_validate(raw)

    logger.warning(
        "Activity %s could not be converted for delivery; skipping.",
        activity_id,
    )
    return None


def _validate_to_field(
    outbound_activity: VultronActivity,
    activity_id: str,
    activity_type: str,
) -> None:
    to_field = getattr(outbound_activity, "to", None)
    if to_field is None or (isinstance(to_field, list) and len(to_field) == 0):
        raise VultronOutboxToFieldMissingError(
            f"Outbound {activity_type} activity '{activity_id}' has no"
            " `to:` field or has an empty `to:` list. All outbound"
            " Vultron activities MUST address at least one recipient via"
            " `to:` (OX-08-001).",
            activity_id=activity_id,
            activity_type=activity_type,
        )


def _warn_secondary_addressing(
    outbound_activity: VultronActivity,
    activity_id: str,
    activity_type: str,
) -> None:
    actor_id = getattr(outbound_activity, "actor", None)
    for addr_field in ("cc", "bto", "bcc"):
        value = getattr(outbound_activity, addr_field, None)
        if value is None or value == []:
            continue
        # CLP-10-001: purposeful self-copy — CaseActor adds its own URI to
        # cc: so ASGI self-delivery routes a copy to its own inbox for ledger
        # archival.  This is intentional; suppress the OX-08-004 warning.
        if addr_field == "cc" and actor_id and value == [actor_id]:
            continue
        logger.warning(
            "Outbound %s activity '%s' has `%s:` set."
            " Vultron direct messages should only use `to:` for"
            " addressing (OX-08-004).",
            activity_type,
            activity_id,
            addr_field,
        )


def _expand_inline_object(
    outbound_activity: VultronActivity,
    activity_id: str,
    activity_type: str,
    activity_object: object,
    dl: DataLayer,
) -> object:
    if activity_type not in _INLINE_OBJECT_ACTIVITY_TYPES:
        return activity_object
    if not isinstance(activity_object, str):
        return activity_object

    logger.warning(
        "Outbound %s activity '%s' has a bare string object_ '%s'."
        " Attempting DataLayer expansion (MV-09-001 violation).",
        activity_type,
        activity_id,
        activity_object,
    )
    full_obj = dl.read(activity_object)
    if full_obj is None:
        return activity_object

    outbound_activity.object_ = full_obj
    logger.debug(
        "Expanded object_ from '%s' to full %s for %s activity '%s' delivery.",
        getattr(full_obj, "id_", activity_object),
        type(full_obj).__name__,
        activity_type,
        activity_id,
    )
    return full_obj


def _validate_inline_object(
    activity_id: str,
    activity_type: str,
    activity_object: object,
) -> None:
    if isinstance(activity_object, (str, as_Link)):
        raise VultronOutboxObjectIntegrityError(
            f"Outbound {activity_type} activity '{activity_id}' has an"
            f" inline object_ that is a bare string or Link"
            f" ({activity_object!r}). Outbound initiating activities must"
            " carry fully inline typed objects (MV-09-001).",
            activity_id=activity_id,
            activity_type=activity_type,
        )


def _recover_typed_inline_object_from_dict(
    activity_object: object,
    activity_type: str,
    activity_id: str,
    outbound_activity: VultronActivity,
) -> object:
    """Reconstruct a typed object from ``dict`` payloads when possible.

    This preserves the queued outbound object payload while enabling the
    downstream ``dl.hydrate()`` path for persistable domain models.
    """
    if not isinstance(activity_object, dict) or isinstance(
        activity_object, BaseModel
    ):
        return activity_object

    obj_type = activity_object.get("type", "")
    if activity_object.keys() <= _STUB_KEYS:
        return activity_object

    model_class = _STUB_OBJECT_MODEL_MAP.get(obj_type)
    if model_class is None:
        return activity_object

    try:
        full_obj = model_class.model_validate(activity_object)
    except (TypeError, ValueError):
        logger.warning(
            "Failed to reconstruct %s model for %s activity '%s';"
            " hydration will be skipped.",
            obj_type,
            activity_type,
            activity_id,
        )
        return activity_object

    outbound_activity.object_ = full_obj
    logger.debug(
        "Recovered typed %s from dict for %s activity '%s'.",
        model_class.__name__,
        activity_type,
        activity_id,
    )
    return full_obj


def _hydrate_inline_object_if_persistable(
    activity_object: object,
    outbound_activity: VultronActivity,
    dl: DataLayer,
) -> object:
    """Hydrate persistable inline objects through the configured ``DataLayer``."""
    from typing import cast

    if not isinstance(activity_object, BaseModel):
        return activity_object
    hydrated_object = dl.hydrate(cast(PersistableModel, activity_object))
    outbound_activity.object_ = hydrated_object
    return hydrated_object
