#!/usr/bin/env python
"""
Inbox processing helpers for the Vultron FastAPI actors router.

Provides the ``parse_activity`` HTTP adapter and the private helpers the
inbox route uses to gate and record receipt of an activity. No route
handlers here. Storing the activity and its inline object is ingress work,
done in ``vultron.adapters.driving.fastapi.inbox_storage`` (#3705).
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
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException, status

from vultron.adapters.driven.actor_hosts import (
    ACTORS_SEGMENT as _ACTORS_SEGMENT,
)
from vultron.adapters.utils import strip_id_prefix
from vultron.core.models.actor import CoreActor
from vultron.core.ports.datalayer import DataLayer, StorableRecord
from vultron.wire.as2.errors import (
    VultronParseError,
    VultronParseMissingTypeError,
)
from vultron.wire.as2.parser import parse_activity as _parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

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
    logger.debug(
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


def _collect_addresses(activity: as_Activity) -> list[str]:
    """Collect all addressee URIs from to/cc/bto/bcc fields."""
    result: list[str] = []
    for field_name in ("to", "cc", "bto", "bcc"):
        val = getattr(activity, field_name, None)
        if val is None:
            continue
        items: list[Any] = val if isinstance(val, list) else [val]
        for item in items:
            if isinstance(item, str):
                result.append(item)
            elif hasattr(item, "id_") and item.id_ is not None:
                result.append(item.id_)
    return result


def _names_an_individual_actor(addr: str) -> bool:
    """Return True if *addr* refers to one specific actor rather than a group.

    IE-11-002 makes resolvability a question about the *address*: an address is
    unresolvable when it "cannot be confirmed to refer to a specific individual
    actor", the given example being a collection URI such as
    ``{case_id}/participants``.  So this asks about the address's shape, and
    deliberately consults no store.

    An earlier reading asked the receiving actor's own DataLayer whether it knew
    the addressee.  That was already a loose proxy for the question, and under
    per-actor storage isolation (ADR-0073) it became a vacuous one: a store
    holds its owner's knowledge, not the node's roster, so a peer is never in it
    and *every* misaddressed Activity naming a real peer fell through to Liberal
    Accept.  IE-11-001 refused nothing.

    Recognised as individual: a bare short id (``"bob"``), and an absolute URI
    whose path ends in ``/actors/{slug}`` — the canonical actor URI shape this
    node mints (``canonical_actor_uri``).  Anything else — a collection URI, a
    sub-collection like ``{actor_id}/followers``, the public addressing
    constant, or a remote node's unfamiliar layout — is unresolvable and so
    falls through to Liberal Accept.
    """
    if not addr:
        return False
    path = urlsplit(addr).path if urlsplit(addr).scheme else addr
    segments = [seg for seg in path.split("/") if seg]
    if len(segments) == 1 and not urlsplit(addr).scheme:
        # A bare short id names one actor, and AC-4 requires it to count.
        return True
    return len(segments) >= 2 and segments[-2] == _ACTORS_SEGMENT


def _activity_addressed_to(
    activity: as_Activity,
    canonical_actor_id: str,
) -> bool:
    """Return True if the Activity addresses canonical_actor_id.

    Absent addressing returns True (Liberal Accept — AC-3, IE-11-002). A
    non-empty address set is checked against the canonical URI and the
    short-ID suffix, so both spellings satisfy the check (AC-4).

    An address that does not name a specific individual actor (e.g. a collection
    URI like ``{case_id}/participants``) is unresolvable and also falls through
    to Liberal Accept (IE-11-002); see :func:`_names_an_individual_actor`.

    The former ``dl`` parameter is gone.  It asked the receiving actor's store
    whether it knew the addressee, and treated "not known" as unresolvable and
    therefore acceptable.  Under ADR-0073 a store holds its *owner's* knowledge
    and never the node's roster, so that lookup answered a question about the
    receiver's acquaintances, not about the address — and it made acceptance
    depend on whichever store the request happened to resolve to.  Resolvability
    is a property of the address itself, which is what
    :func:`_names_an_individual_actor` decides.

    The inbox route (``add_item_to_actor_inbox``) gates on this and returns 400
    when it is False, so a change here changes what the node refuses.
    """
    addresses = _collect_addresses(activity)
    if not addresses:
        return True
    canonical_short = strip_id_prefix(canonical_actor_id)
    for addr in addresses:
        if (
            addr == canonical_actor_id
            or strip_id_prefix(addr) == canonical_short
        ):
            return True
    # Refuse only on provable exclusion: every address must be one we can
    # confirm names some *other* individual actor.  One unresolvable address is
    # enough uncertainty to accept the whole thing.
    return not all(_names_an_individual_actor(addr) for addr in addresses)


def _activity_already_received(actor: CoreActor, activity_id: str) -> bool:
    return bool(
        getattr(actor, "inbox", None)
        and hasattr(getattr(actor, "inbox", None), "items")
        and activity_id in getattr(actor, "inbox").items
    )


def _get_body(body: dict[str, Any]) -> dict[str, Any]:
    """FastAPI dependency: return the raw JSON request body dict."""
    return body


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
