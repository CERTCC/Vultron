"""Actor registry routes: list actors, create a hosted actor, register a peer."""

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

import logging
from typing import Any, Literal, cast
from urllib.parse import urlsplit

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from pydantic import BaseModel, Field

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.deps import (
    get_act_clock,
    get_actor_dl,
    node_base_url,
    node_db_url_template,
)
from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.adapters.driving.fastapi.routers.actors._lookup import (
    _ACTOR_TYPE_MAP,
    _actor_class_for_record,
    _find_actor_record,
    _find_actor_record_by_id,
    _resolve_actor_or_404,
    profile_of_record,
)
from vultron.adapters.utils import strip_id_prefix
from vultron.config import get_config
from vultron.core.behaviors.bridge.act_instant import stamp_arrival
from vultron.core.models._helpers import authored_times, new_object_id
from vultron.core.models.actor import (
    CoreActor,
    VultronOrganization,
    hosted_endpoints,
)
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.clock import ClockPort
from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger("uvicorn.error")


AnyActor = CoreActor


router = APIRouter(prefix="/actors", tags=["Actors"])


@router.get(
    "/",
    description="Returns a list of Actor examples.",
    operation_id="actors_list",
)
def get_actors(http_request: Request):
    """Returns the actors this node hosts.

    Under ADR-0073 this enumerates hosted actors and reads each one's record
    from its own store.  It previously scanned a shared pool for every
    actor-typed row, which also returned the node's *peers* — actors it merely
    holds an address for.  A peer is not hosted here, so peers are no longer
    listed (ADR-0073#hosted-actors-list-only).

    The actors are enumerated from, and each store is opened in, the serving
    app's own deployment (:func:`node_db_url_template`, :func:`node_base_url`),
    so a node lists only its own actors even when other nodes run in the same
    process, and the records listed are the ones the rest of this app's routes
    read (DL-07-007, DL-07-011).
    """
    db_url = node_db_url_template(http_request)
    profiles: list[dict[str, Any]] = []
    for actor_id in actor_hosts.hosted_actor_ids(
        db_url, node_base_url(http_request)
    ):
        actor_dl = get_datalayer(actor_id, db_url=db_url)
        record = _find_actor_record(actor_dl, actor_id)
        if record is not None:
            # Each hosted actor is listed as the profile it publishes, key
            # included (ENC-01-002), not as its bare stored record.
            profiles.append(profile_of_record(record))

    logger.debug("get_actors: found %d hosted actor(s)", len(profiles))

    return AS2JSONResponse(profiles)


class ActorCreateRequest(BaseModel):
    """Request body for ``POST /actors/`` (D5-1-G2).

    Creates a new actor record in that actor's own store.  The operation is
    idempotent: if ``id`` is supplied and an actor with that URI already
    exists, the existing record is returned with HTTP 200.
    """

    name: str = Field(description="Display name of the actor.")
    actor_type: Literal[
        "Person", "Organization", "Service", "Application", "Group"
    ] = Field(
        default="Organization",
        description="ActivityStreams actor type.",
    )
    id_: str | None = Field(
        default=None,
        alias="id",
        description=(
            "Full URI for the actor.  Omit to let the server derive one "
            "from ``VULTRON_SERVER__BASE_URL``."
        ),
    )

    model_config = {"populate_by_name": True}


def _is_foreign_authority(actor_id: str, base_url: str | None) -> bool:
    """Return ``True`` when *actor_id* is under a different authority than this node.

    A foreign-authority id carries a scheme but names a process on another host.
    ``canonical_actor_uri`` strips the trailing slash from any scheme-bearing id
    (OID-01-005) but preserves the authority (netloc) intact
    (ADR-0073#peer-records-in-knowers-store).  ``POST /actors/`` must still reject
    foreign-authority ids: peers are address-book entries in a hosted actor's own
    store, not hosted actors in their own right (ADR-0081).

    Args:
        actor_id: The already-canonicalized actor URI.
        base_url: This node's base URL, or ``None`` to fall back to config.
    """
    parsed_id = urlsplit(actor_id)
    if not parsed_id.scheme:
        return False

    effective_base = base_url or get_config().server.base_url
    return parsed_id.netloc != urlsplit(effective_base).netloc


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create Actor",
    description=(
        "Creates a new actor record in that actor's own store. "
        "Idempotent: if an actor with the same ``id`` already exists the "
        "existing record is returned with HTTP 200. "
        "Rejects ids from a foreign authority with 422; use "
        "``POST /actors/{actor_id}/peers/`` to register a peer."
    ),
    operation_id="actors_create",
)
def create_actor(
    request: ActorCreateRequest,
    http_request: Request,
    clock: ClockPort = Depends(get_act_clock),
):
    """Create (or return existing) hosted actor record in that actor's own store.

    An actor is a process with API endpoints, and its id **is** the URL that
    reaches it: an actor this node hosts is named
    ``{base_url}/actors/{slug}``, and its inbox is ``{id}/inbox``. So the id is
    canonicalized *before* the record is built, not only when choosing the store.

    An unspecified id becomes a fresh **slug**, not a generated URI. A
    generated URI already carries a scheme and a base, and
    ``canonical_actor_uri`` normalises such a value (strips a trailing slash)
    without adopting this node's base, so unless it was built on exactly that
    base the record's id would name an endpoint this node does not serve: its
    store would be reachable under one id and ``GET /actors/{slug}`` would
    resolve to another. Handing the canonicalizer a bare slug is what makes the
    id and the serving endpoint the same string by construction
    (ADR-0073#url-segment-computed-not-looked-up).

    A client-supplied id under a **foreign** authority is rejected with 422.
    Peers are not hosted actors — they are address-book entries inside each hosted
    actor's own store (ADR-0081).  The correct route is
    ``POST /actors/{hosted_actor_id}/peers/``.

    "This node's namespace" is the *serving app's* base URL where it declares one
    (``deps.node_base_url``), falling back to configuration. Creating an actor and
    then addressing it have to agree on that namespace, or the record lands in a
    store no request can reach.

    The same agreement is needed on the *storage deployment*: the subject actor
    is named in the body, so there is no path segment to hang an injectable
    per-actor dependency on, and the store is opened directly. Opening it in the
    serving app's deployment (``deps.node_db_url_template``) rather than the
    process-global one is what keeps this route reading the same stores as the
    rest of the app when several nodes share a process.
    """
    base_url = node_base_url(http_request)
    try:
        actor_id = actor_hosts.canonical_actor_uri(
            # The slug is the UUID of a freshly minted id (OID-01-004).
            request.id_ or strip_id_prefix(new_object_id()),
            base_url=base_url,
        )
    except ValueError as exc:
        # A client-supplied id that names no actor (``"/"``, ``"//"``) is a bad
        # request, not a server fault: it must not become a 500, and it must not
        # be allowed to mint a store for a phantom actor.
        raise HTTPException(  # noqa: B904  # ruff-baseline #3353
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )
    if _is_foreign_authority(actor_id, base_url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Actor id {actor_id!r} is under a foreign authority. "
                "Use POST /actors/{hosted_actor_id}/peers/ to register a peer."
            ),
        )
    datalayer = get_datalayer(
        actor_id, db_url=node_db_url_template(http_request)
    )

    # Idempotency: return existing record unchanged.
    existing = _find_actor_record(datalayer, actor_id)
    if existing is not None:
        cls = _actor_class_for_record(existing)
        data = existing.get("data_", {})
        return AS2JSONResponse(
            cls.model_validate(data).model_dump(
                mode="json", by_alias=True, exclude_none=True
            ),
            status_code=status.HTTP_200_OK,
        )

    actor_cls = _ACTOR_TYPE_MAP.get(request.actor_type, VultronOrganization)
    # Authored when the request arrives: one clock read (ADR-0176).
    actor = actor_cls(
        id_=actor_id,
        name=request.name,
        **hosted_endpoints(actor_id),
        **authored_times(stamp_arrival(clock)),
    )
    datalayer.create(object_to_record(cast(PersistableModel, actor)))
    logger.info("Created actor %s (type=%s)", actor_id, request.actor_type)
    return AS2JSONResponse(
        actor.model_dump(mode="json", by_alias=True, exclude_none=True),
        status_code=status.HTTP_201_CREATED,
    )


class PeerRegisterRequest(BaseModel):
    """Request body for ``POST /actors/{actor_id}/peers/``.

    Registers a peer actor's address-book entry inside *actor_id*'s own store.
    The peer is not hosted here; its id is the URL outbound delivery posts to.
    """

    id_: str = Field(
        alias="id",
        description="Full absolute URI of the peer actor (http/https).",
    )
    name: str = Field(description="Display name of the peer actor.")
    actor_type: Literal[
        "Person", "Organization", "Service", "Application", "Group"
    ] = Field(
        default="Organization",
        description="ActivityStreams actor type.",
    )

    model_config = {"populate_by_name": True}


@router.post(
    "/{actor_id:path}/peers/",
    status_code=status.HTTP_201_CREATED,
    summary="Register Peer",
    description=(
        "Record a peer actor's address-book entry inside the named hosted "
        "actor's own store (ADR-0081).  The peer is not hosted here; its id "
        "is the URL outbound delivery posts to. Idempotent: if the peer is "
        "already known, the existing record is returned with HTTP 200."
    ),
    operation_id="actors_register_peer",
)
def register_peer(
    actor_id: str,
    request: PeerRegisterRequest,
    datalayer: DataLayer = Depends(get_actor_dl),
):
    """Record *request.id_* as a known peer in *actor_id*'s own store.

    The host actor must exist on this node (404 otherwise).  The peer id must
    be an absolute http/https URI (422 otherwise) — it is the address outbound
    delivery posts to, so anything else would mint an unreachable participant.

    Peers are **not** hosted actors.  They do not appear in ``GET /actors/``,
    they do not get their own per-actor store, and they must not be created via
    ``POST /actors/``.  A peer is knowledge a hosted actor holds about the world
    — the Actor Knowledge Model (AKM) in one sentence.
    """
    peer_id = request.id_
    parsed = urlsplit(peer_id)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Peer id {peer_id!r} is not a deliverable URI. "
                "A peer id must be an absolute http(s) URI."
            ),
        )

    # The host actor must be present on this node.
    _resolve_actor_or_404(actor_id, datalayer)

    # Idempotency: use exact-id lookup — _find_actor_record falls back to
    # datalayer.actor_id (the host) as a candidate, so it would find the host
    # actor itself instead of an absent peer.
    existing = _find_actor_record_by_id(datalayer, peer_id)
    if existing is not None:
        cls = _actor_class_for_record(existing)
        data = existing.get("data_", {})
        return AS2JSONResponse(
            cls.model_validate(data).model_dump(
                mode="json", by_alias=True, exclude_none=True
            ),
            status_code=status.HTTP_200_OK,
        )

    actor_cls = _ACTOR_TYPE_MAP.get(request.actor_type, VultronOrganization)
    # Only what the request supplied: no clock time and no endpoint derived
    # from the id, since the peer stated neither (AKM-02-006, ADR-0159).
    # Delivery falls back to the derived inbox address on its own (OX-12-010).
    peer = actor_cls(
        id_=peer_id, name=request.name, published=None, updated=None
    )
    datalayer.create(object_to_record(cast(PersistableModel, peer)))
    logger.info("Registered peer %s in actor %s store", peer_id, actor_id)
    return AS2JSONResponse(
        peer.model_dump(mode="json", by_alias=True, exclude_none=True),
        status_code=status.HTTP_201_CREATED,
    )
