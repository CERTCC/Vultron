#!/usr/bin/env python
"""
Inbox processing helpers for the Vultron FastAPI actors router.

Provides the inbox's two ingress stages, :func:`verified_delivery` (decode
and verify the body's proofs, SIG-03-003) and the ``parse_activity`` HTTP
adapter, and the private addressing helpers the inbox route uses to gate an
activity. No route handlers here.
Rebuilding the activity for routing is ingress work, done in
``vultron.adapters.driving.fastapi.inbox_orchestration`` with
``inbox_staging``, which writes nothing to the receiver's store (DL-06-006),
and that is also where a redelivered activity is detected (IE-10-001); the
route keeps no receipt bookkeeping of its own (IE-02-004).
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
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, status
from starlette.concurrency import run_in_threadpool

from vultron.adapters.driven.actor_hosts import (
    ACTORS_SEGMENT as _ACTORS_SEGMENT,
    canonical_actor_uri,
)
from vultron.adapters.driving.fastapi.deps import (
    get_actor_dl,
    get_actor_profile_fetcher,
    node_base_url,
)
from vultron.adapters.driving.fastapi.errors import (
    inbox_body_http_exception,
    translate_domain_errors,
)
from vultron.adapters.driving.fastapi.inbox_verification import (
    ProfileKeyProofVerifier,
    decode_inbox_body,
)
from vultron.adapters.driving.fastapi.routers.actors._lookup import (
    _resolve_actor_or_404,
)
from vultron.adapters.utils import strip_id_prefix
from vultron.core.models.actor import CoreActor
from vultron.core.ports.actor_profile_fetch import ActorProfileFetchPort
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.proof_verification import ProofVerificationPort
from vultron.errors import VultronProofVerificationError
from vultron.wire.as2.errors import (
    VultronParseError,
    VultronParseMissingTypeError,
    VultronUnsignableJsonError,
)
from vultron.wire.as2.parser import parse_activity as _parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class VerifiedDelivery:
    """A delivery whose body decoded and whose proofs verified.

    Attributes:
        body: The decoded JSON object, as received; the parser reads it next.
        receiver: The addressed actor, found before any key is looked up.
    """

    body: dict[str, Any]
    receiver: CoreActor


def get_proof_verifier(
    actor_id: str,
    request: Request,
    dl: DataLayer = Depends(get_actor_dl),
    fetcher: ActorProfileFetchPort = Depends(get_actor_profile_fetcher),
) -> ProofVerificationPort:
    """FastAPI dependency: the verification stage's port.

    The real stage, :class:`ProfileKeyProofVerifier`, over the addressed
    actor's store and the app's profile fetch.  The receiver it names on a
    fetch is the canonical URI of the path segment, as ``get_actor_dl``
    computes it.  A test that is not about verification may override this
    seam with ``test.support.signing.AcceptingProofVerifier``.
    """
    receiver_id = canonical_actor_uri(
        actor_id, base_url=node_base_url(request)
    )
    return ProfileKeyProofVerifier(dl, fetcher, receiver_id)


async def verified_delivery(
    actor_id: str,
    request: Request,
    dl: DataLayer = Depends(get_actor_dl),
    verifier: ProofVerificationPort = Depends(get_proof_verifier),
) -> VerifiedDelivery:
    """FastAPI dependency: the inbox's decode and verification stage.

    Runs before ``parse_activity``, so a forged body reaches no expansion,
    validation or hydration (SIG-03-001, SIG-03-003).  The addressed actor
    is found first, so a post to an actor this node does not host is
    answered 404 with no key lookup.  The raw body is decoded with
    :func:`~vultron.adapters.driving.fastapi.inbox_verification.decode_inbox_body`
    and every proof it needs is checked by the verifier
    (:func:`get_proof_verifier`, SIG-02-001, SIG-04-002).

    Raises:
        HTTPException: 404 for an actor this node does not host; 400 for a
            body that is not JSON (IE-07-001); 422 for JSON the inbox
            refuses (IE-04-002); 422 ``ProofVerificationError`` for a proof
            that is missing or does not verify, or whose key cannot be read
            (SIG-03-002, EH-03-005).
    """
    # Store reads and the JSON decode are blocking work: off the event loop.
    receiver = await run_in_threadpool(_resolve_actor_or_404, actor_id, dl)
    raw = await request.body()
    try:
        body = await run_in_threadpool(decode_inbox_body, raw)
        await verifier.verify(body)
    except VultronUnsignableJsonError as exc:
        logger.warning(
            "Refusing a delivery to actor_id=%s: its body cannot be read"
            " as one JSON object: %s",
            receiver.id_,
            exc,
        )
        raise inbox_body_http_exception(exc) from exc
    except VultronProofVerificationError as exc:
        # The id and actor are the unverified sender's claims.
        logger.warning(
            "Refusing activity %s (claimed actor %s) to actor_id=%s: %s",
            body.get("id"),
            body.get("actor"),
            receiver.id_,
            exc,
        )
        raise translate_domain_errors(exc) from exc
    return VerifiedDelivery(body=body, receiver=receiver)


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
        raise HTTPException(  # noqa: B904  # ruff-baseline #3353
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except VultronParseError as exc:
        raise HTTPException(  # noqa: B904  # ruff-baseline #3353
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
