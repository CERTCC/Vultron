#!/usr/bin/env python
"""
Inbox processing helpers for the Vultron FastAPI actors router.

Provides the ``parse_activity`` HTTP adapter and a set of private
helpers that prepare and persist inbox items before dispatching them
to background processing. No route handlers here.
"""

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

import json
import logging
from typing import Any, cast

from fastapi import HTTPException, status
from pydantic import ValidationError

from vultron.adapters.driven.db_record import object_to_record
from vultron.core.models.actor import CoreActor
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import DataLayer, StorableRecord
from vultron.wire.as2.errors import (
    VultronParseError,
    VultronParseMissingTypeError,
)
from vultron.wire.as2.parser import parse_activity as _parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

logger = logging.getLogger("uvicorn.error")


def parse_activity(body: dict[str, Any]) -> as_Activity:
    """HTTP adapter: parse request body and map wire errors to HTTP responses.

    Delegates AS2 parsing to the wire layer and converts domain parse errors
    into appropriate HTTP status codes for FastAPI.

    Args:
        body: The request body as a dictionary.

    Returns:
        A typed as_Activity subclass instance.

    Raises:
        HTTPException: 400 if the `type` field is missing; 422 for all other
            parse failures (unknown type, validation error).
    """
    logger.info(
        "Parsing activity from request body (type=%r):\n%s",
        body.get("type"),
        json.dumps(body, indent=2, default=str),
    )
    try:
        return _parse_activity(body)
    except VultronParseMissingTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except VultronParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )


def _activity_already_received(actor: CoreActor, activity_id: str) -> bool:
    return bool(
        getattr(actor, "inbox", None)
        and hasattr(getattr(actor, "inbox", None), "items")
        and activity_id in getattr(actor, "inbox").items
    )


def _get_body(body: dict[str, Any]) -> dict[str, Any]:
    """FastAPI dependency: return the raw JSON request body dict."""
    return body


def _reparse_as_specific_type(
    nested: as_Object,
    raw_obj: dict[str, Any],
) -> PersistableModel:
    """Re-parse *raw_obj* with the correct specific vocabulary class.

    When the wire parser validates an inline object as the base ``as_Object``
    type, domain-specific fields are silently dropped.  This helper looks up
    the specific vocabulary class for ``nested.type_`` and re-parses
    *raw_obj* (the raw dict from the wire body) with it so all fields are
    preserved.

    Returns the re-parsed specific instance, or the original *nested* cast
    to ``PersistableModel`` when re-parsing fails or is unnecessary.
    """
    base: PersistableModel = cast(PersistableModel, nested)
    obj_type: str | None = nested.type_
    if obj_type is None:
        return base
    try:
        specific_cls = find_in_vocabulary(obj_type)
    except KeyError:
        return base
    if isinstance(nested, specific_cls):
        return base
    try:
        result = cast(PersistableModel, specific_cls.model_validate(raw_obj))
        logger.debug(
            "Re-parsed inline '%s' as specific class %s.",
            obj_type,
            specific_cls.__name__,
        )
        return result
    except ValidationError:
        logger.debug(
            "Could not re-parse inline '%s' as %s; using base as_Object.",
            obj_type,
            specific_cls.__name__,
        )
        return base


def _store_nested_inbox_object(
    dl: DataLayer,
    activity: as_Activity,
    body: dict[str, Any] | None = None,
) -> None:
    """Store the inline nested ``object_`` of an inbox activity.

    When the wire parser parses an Announce or other transitive activity, the
    inline ``object_`` is validated as the base ``as_Object`` type, which
    silently drops domain-specific fields (``case_id``, ``event_type``, etc.).
    This function uses the raw request body to re-parse the nested object with
    the correct specific vocabulary class so that all fields are preserved.
    Without this, a subsequent DataLayer round-trip would fail Pydantic
    validation on the specific class (missing required fields), causing
    rehydration to return ``None`` and pattern matching to fall back to a
    less specific pattern (e.g. ``announce_vulnerability_case`` instead of
    ``announce_case_ledger_entry``).

    The re-parsed object is also written back to ``activity.object_`` so that
    the in-memory activity already carries the fully-typed nested object.
    This lets ``FastAPIIngressAdapter.rehydrate()`` pass the activity object
    directly to ``rehydrate()`` without a DataLayer round-trip, preserving
    domain-specific fields that would otherwise be lost via dehydration.

    Args:
        dl: The shared DataLayer for storing the nested object.
        activity: The parsed AS2 activity whose ``object_`` to store.
        body: Optional raw JSON request body dict.  When present, used to
            re-parse the nested object with the correct specific class.
    """
    nested = getattr(activity, "object_", None)
    if nested is None or isinstance(nested, str):
        return
    if not (
        hasattr(nested, "id_")
        and hasattr(nested, "type_")
        and nested.type_ is not None
        and not nested.type_.startswith("as_")
    ):
        return

    raw_obj = body.get("object") if body is not None else None
    typed_nested: PersistableModel = (
        _reparse_as_specific_type(nested, raw_obj)
        if isinstance(raw_obj, dict)
        else cast(PersistableModel, nested)
    )

    # Write the specifically-typed object back onto the in-memory activity so
    # that FastAPIIngressAdapter.rehydrate() can operate on the already-typed
    # object without going through a DataLayer round-trip (which would
    # dehydrate the inline object to a string ID and lose domain fields).
    cast(Any, activity).object_ = typed_nested

    # CaseLedgerEntry objects must NOT be stored here: they are stored
    # canonically by PersistReceivedLogEntryNode after effects are applied
    # (SYNC-12-001/SYNC-12-003).  Pre-storing them would cause
    # CheckLedgerEntryAlreadyStoredNode to skip effects on first delivery.
    if getattr(typed_nested, "type_", None) == "CaseLedgerEntry":
        logger.debug(
            "Skipping parse-time store of inline CaseLedgerEntry '%s' "
            "(deferred to PersistReceivedLogEntryNode).",
            getattr(typed_nested, "id_", "?"),
        )
        return

    try:
        dl.create(object_to_record(typed_nested))
    except ValueError:
        pass


def _store_inbox_activity(dl: DataLayer, activity: as_Activity) -> None:
    try:
        dl.create(object_to_record(activity))
    except ValueError:
        logger.debug(
            "Activity %s already exists in shared DL; skipping re-store.",
            activity.id_,
        )


def _record_inbox_receipt(
    dl: DataLayer,
    actor: CoreActor,
    activity_id: str,
    canonical_actor_id: str,
) -> None:
    inbox = getattr(actor, "inbox", None)
    if not inbox or not hasattr(inbox, "items"):
        return

    inbox.items.append(activity_id)
    dl.update(
        actor.id_,
        StorableRecord(
            id_=actor.id_,
            type_=getattr(actor, "type_", None) or "Actor",
            data_=actor.model_dump(mode="json"),
        ),
    )
    logger.debug(
        f"Added activity {activity_id} to actor {canonical_actor_id} inbox record"
    )
