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
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""
Provides a backend API router for basic Vultron data layer operations.
"""

import json
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driving.fastapi.deps import (
    get_actor_dl,
    get_hosted_actor_dls,
)
from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.adapters.received_archive import (
    read_held_as_received,
    read_received_as_received,
)
from vultron.adapters.utils import full_object_id
from vultron.core.models.actor import CoreActor
from vultron.core.models.base import CoreObject
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer, StorableRecord
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.rehydration import rehydrate
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.collections import (
    as_OrderedCollection,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)
from vultron.wire.as2.vocab.objects.vultron_actor import (
    as_VultronApplication,
    as_VultronGroup,
    as_VultronOrganization,
    as_VultronPerson,
    as_VultronService,
)

# Debug/inspection views are actor-scoped: under ADR-0073 there is no "the"
# store to inspect, and a node may host several actors (a vendor plus the
# CaseActors it self-hosts under CP-08-003).  Naming the actor in the path keeps
# ADR-0058 causal gates honest — a gate must assert that *a named actor* has
# committed some state, not merely that some actor in the container has.
router = APIRouter(prefix="/actors/{actor_id}/datalayer", tags=["datalayer"])

#: Node-level operations that legitimately span every hosted actor.  These are
#: operator actions on the process (like a restart), not one actor reading
#: another's data through the protocol.
admin_router = APIRouter(prefix="/admin/datalayer", tags=["datalayer"])


_OFFER_TYPE = "Offer"


def _read_offer(datalayer: DataLayer, offer_id: str) -> as_Offer | None:
    """The Offer *offer_id* as this actor holds it, or ``None``.

    Read as :func:`~vultron.adapters.received_archive.read_held_as_received`
    reads any activity this actor holds: a received one parsed from the body
    its archive record keeps, under a key the receiver derives from the
    sender's id (CLP-10-017, ADR-0149), since a receiver holds no received
    activity under the sender's id (DL-06-006); otherwise the row under
    *offer_id*, where an Offer the actor authored is stored.  *offer_id* may
    be a bare UUID, as the store's own lookup allows.

    Whatever is held under the id must be an Offer: every Offer a store holds
    is an ``as_Offer``, read back as its own class (ADR-0034) or parsed from
    its archived body, and ``as_Invite`` subclasses ``as_Offer`` but types
    itself ``Invite``, so a received Invite is not served as one.
    """
    try:
        held = read_held_as_received(
            cast(CasePersistence, datalayer),
            full_object_id(offer_id),
            _OFFER_TYPE,
        )
    except VultronNotFoundError:
        return None
    if not isinstance(held, as_Offer) or held.type_ != _OFFER_TYPE:
        return None
    return held


def _received_offers(datalayer: DataLayer) -> dict[str, as_Activity]:
    """Every Offer this actor received, keyed by the sender's id for it.

    Each is parsed from the body its archive record keeps, through the seam
    that reads a held body (:func:`read_received_as_received`), so the list
    and the single-Offer reads answer one received Offer the same way
    (CLP-10-017, ADR-0149).  The record is listed before it is read, so the
    read cannot miss.
    """
    return {
        record.activity_id: read_received_as_received(
            cast(CasePersistence, datalayer), record.activity_id, _OFFER_TYPE
        )
        for record in datalayer.list_objects(ReceivedActivityRecord.__name__)
        if isinstance(record, ReceivedActivityRecord)
        and json.loads(record.received_body).get("type") == _OFFER_TYPE
    }


def _concerns_actor(offer: as_Offer, actor_uri: str) -> bool:
    """Whether *offer* is addressed to, or was sent by, *actor_uri*.

    Ids are compared whole: a recipient whose id merely ends with the actor's
    is a different actor.
    """
    recipients = offer.to if isinstance(offer.to, list) else [offer.to]
    addressed = {getattr(r, "id_", r) for r in recipients if r is not None}
    sender = getattr(offer.actor, "id_", offer.actor)
    return actor_uri in addressed or sender == actor_uri


def _serve_stored(obj: PersistableModel) -> AS2JSONResponse | dict[str, Any]:
    """Serve *obj* as the store holds it, without rebuilding it.

    ``dl.read()`` already returns the typed object (ADR-0034), and a
    ``CoreObject`` is its own AS2 class (ADR-0099), so it renders as AS2
    directly.  Rebuilding it from its dump ran its construction validators
    again, and a validator that seeds a default drew an id and read the
    clock: a read then shifted every id a seeded demo run minted after it
    (#5510).  A bookkeeping row that has no AS2 form is served as its plain
    dump.
    """
    if isinstance(obj, (as_Base, CoreObject)):
        return AS2JSONResponse(obj)
    # JSON mode, so a bookkeeping row's own serializers run and every time it
    # carries is answered in the fixed form (CS-13-007).
    return obj.model_dump(mode="json", by_alias=True, serialize_as_any=True)


# Declared ahead of ``/{object_type}/{object_id}``: routes match in
# declaration order, and that pattern would otherwise answer every
# ``/Offers/{offer_id}`` request, so this route was never reached.
@router.get(
    "/Offers/{offer_id}",
    response_model=as_Offer,
    description=(
        "Returns an Offer the actor received or sent, by actor id and offer"
        " id."
    ),
    operation_id="datalayer_get_actor_offer",
)
def get_actor_offer(
    actor_id: str, offer_id: str, datalayer: DataLayer = Depends(get_actor_dl)
) -> AS2JSONResponse:
    obj = _read_offer(datalayer, offer_id)

    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # ``actor_id`` is the raw path segment; compare the canonical URI the
    # store was opened for (ADR-0073), as ``get_actor_outbox`` does.
    if not _concerns_actor(obj, actor_hosts.canonical_actor_uri(actor_id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Served as held, as the by-id reads serve it through ``_serve_stored``
    # (#5510): rebuilding it as the declared ``as_Offer`` narrowed a semantic
    # Offer's inline object to the base type and dropped that object's own
    # fields (#5540).  An ``as_Offer`` always has an AS2 form, so this route
    # returns the response class directly rather than through
    # ``_serve_stored``: a plain dump would be filtered through
    # ``response_model`` and narrowed again (HTTP-09-002).
    # ``response_model`` still documents the shape in the OpenAPI schema.
    return AS2JSONResponse(obj)


@router.get(
    "/{object_type}/{object_id}",
    description="Returns a specific object by type and ID.",
    operation_id="datalayer_get_by_type_and_id",
)
def get_object(
    object_type: str,
    object_id: str,
    datalayer: DataLayer = Depends(get_actor_dl),
):
    # A key that holds one ``/`` (a ``VultronOfferRecord`` id, say) also fits
    # this pattern, and the ``{key:path}`` route below never sees a two-segment
    # path.  When the part after the slash names nothing, read the whole path
    # as the key, so a record whose key holds one ``/`` is readable by it
    # (#5529).  The suffix is still read first, so every URL that resolved
    # before resolves to the same row; a key whose suffix also names a row is
    # therefore still shadowed by it.  Every record keyed this way
    # percent-quotes its suffix (``VultronOfferRecord.build_id``), so no stored
    # key collides with a bare object id.
    obj = datalayer.read(object_id) or datalayer.read(
        f"{object_type}/{object_id}"
    )

    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return _serve_stored(obj)


@router.get(
    "/Offer/",
    response_model=as_Offer,
    operation_id="datalayer_get_offer",
)
def get_offer(
    object_id: str, datalayer: DataLayer = Depends(get_actor_dl)
) -> AS2JSONResponse:
    obj = _read_offer(datalayer, object_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    # Served as held, as ``get_actor_offer`` serves it (#5540).
    return AS2JSONResponse(obj)


@router.get(
    "/Report/",
    response_model=as_VulnerabilityReport,
    operation_id="datalayer_get_report",
)
def get_report(
    id: str, datalayer: DataLayer = Depends(get_actor_dl)
) -> AS2JSONResponse:
    # Served as stored (#5510): ``VulnerabilityReport`` is its own AS2 class
    # (ADR-0099), so a rebuild from its dump would add nothing.
    obj = datalayer.read(id)
    if not isinstance(obj, as_VulnerabilityReport):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return AS2JSONResponse(obj)


@router.get(
    "/",
    description=(
        "Returns the entire contents of the datalayer, or, given one or more"
        " `type` parameters, only the objects of those types."
    ),
    operation_id="datalayer_list",
)
def get_datalayer_contents(
    datalayer: DataLayer = Depends(get_actor_dl),
    types: Annotated[list[str] | None, Query(alias="type")] = None,
) -> dict[str, Any]:
    """Return every stored object, keyed by id, as plain JSON.

    The store holds bare ``CoreRecord`` bookkeeping rows beside AS2 objects,
    so the whole-store dump is not an AS2 document and is served as
    ``application/json`` rather than through ``AS2JSONResponse``
    (ARCH-20-006).

    One or more ``type`` query parameters narrow the dump to objects of those
    types, each serialized exactly as the whole-store dump serializes it.  A
    poll that looks for one kind of object reads only that kind: rehydrating
    and serializing the whole store on every poll slowed the container it
    polled as the store grew (#4600).  A type the store holds no object of
    contributes nothing, so an unknown or misspelled name yields an empty
    mapping rather than an error: the store cannot tell a type it has no rows
    for from one that does not exist.
    """
    data: dict[str, PersistableModel] | list[StorableRecord]
    if types:
        data = {
            obj.id_: obj
            for type_key in types
            for obj in datalayer.list_objects(type_key)
        }
    else:
        data = datalayer.all()
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return {
        k: v.model_dump(mode="json", exclude_none=True, by_alias=True)
        for k, v in data.items()
    }


@router.get(
    "/Offers/",
    description=(
        "Returns all Offer objects: the Offers the actor authored and those it"
        " received, each received one keyed by the sender's id for it."
    ),
    operation_id="datalayer_list_offers",
)
def get_offers(
    datalayer: DataLayer = Depends(get_actor_dl),
) -> AS2JSONResponse:
    # A received Offer is served from its archive record, which replaces any
    # row held under the sender's id for the same Offer (DL-06-006).  Each is
    # served as held, as ``get_actor_offer`` serves it: rebuilding it as the
    # base ``as_Offer`` dropped the fields of a semantic Offer's inline
    # object (#5540).
    #
    # The authored Offers come from one typed listing, not a read per row:
    # ``list_objects`` reconstructs a row exactly as ``dl.read`` does, so the
    # list and the by-id read still agree, while a read per row grew the cost
    # of a poll with the store (#4600) and turned a row the store reads as
    # absent into a 500 for the whole list.
    offers: dict[str, PersistableModel | as_Activity] = {
        obj.id_: obj for obj in datalayer.list_objects(_OFFER_TYPE)
    }
    offers |= _received_offers(datalayer)

    return AS2JSONResponse(
        {
            offer_id: offer.model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            for offer_id, offer in offers.items()
        }
    )


@router.get(
    "/Reports/",
    description="Returns all as_VulnerabilityReport objects.",
    operation_id="datalayer_list_reports",
)
def get_reports(
    datalayer: DataLayer = Depends(get_actor_dl),
) -> AS2JSONResponse:
    results = datalayer.by_type("VulnerabilityReport")

    return AS2JSONResponse(
        {
            k: as_VulnerabilityReport.model_validate(v).model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            for k, v in results.items()
        }
    )


_DATALAYER_ACTOR_TYPE_MAP: dict[str, type[as_Actor | CoreActor]] = {
    "Person": as_VultronPerson,
    "Organization": as_VultronOrganization,
    "Service": as_VultronService,
    "Application": as_VultronApplication,
    "Group": as_VultronGroup,
}


def _actor_class_for_payload(
    payload: dict[str, Any],
) -> type[as_Actor | CoreActor]:
    payload_type = payload.get("type_") or payload.get("type")
    if isinstance(payload_type, str):
        return _DATALAYER_ACTOR_TYPE_MAP.get(payload_type, as_Actor)
    return as_Actor


@router.get(
    "/Actors/",
    description="Returns all Actor objects.",
    operation_id="datalayer_list_actors",
)
def get_actors(
    datalayer: DataLayer = Depends(get_actor_dl),
):
    results = datalayer.by_type("Actor")

    return AS2JSONResponse(
        {
            k: _actor_class_for_payload(v)
            .model_validate(v)
            .model_dump(mode="json", by_alias=True, exclude_none=True)
            for k, v in results.items()
        }
    )


@router.get(
    "/outbox/",
    description="Returns the outbox of a specific Actor.",
    response_model=as_OrderedCollection,
    operation_id="datalayer_get_actor_outbox",
)
def get_actor_outbox(
    actor_id: str, datalayer: DataLayer = Depends(get_actor_dl)
) -> AS2JSONResponse:
    # ``actor_id`` is the raw URL path segment, not an object id.  Resolve it the
    # same way ``get_actor_dl`` just did (ADR-0073) — reading the store with the
    # bare segment always misses, and the endpoint would 404 for an actor whose
    # store it is holding open.
    canonical_id = actor_hosts.canonical_actor_uri(actor_id)
    actor_obj = datalayer.read(canonical_id)

    if not actor_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # dl.read() now returns a CoreActor whose outbox field is a plain URI
    # string (ADR-0034 / PR #1512).  The old as_Actor.model_validate() path
    # converted that URI to an empty as_OrderedCollection with no items.
    # Instead, query the DataLayer queue directly for the actor's outbox IDs.
    activity_ids = cast(CaseOutboxPersistence, datalayer).outbox_list()

    # ``published``/``updated`` are passed as ``None`` rather than left to
    # ``as_Object``'s ``default_factory=now_utc``: this collection is a view
    # the read synthesises, not a stored object, so a read that stamped it
    # would read the clock and invent a time for a thing that has none
    # (#5510).  ``AS2JSONResponse`` excludes ``None``, so neither key is
    # serialised.  The clock read was invisible while every stamp was a whole
    # second; keeping microseconds made it show (#5452).
    outbox = as_OrderedCollection(
        id_=f"{canonical_id}/outbox",
        items=[
            rehydrate(activity_id, dl=datalayer)
            for activity_id in activity_ids
        ],
        published=None,
        updated=None,
    )

    return AS2JSONResponse(outbox)


@router.get(
    "/{object_type}s/",
    description="Returns all objects of a given type.",
    operation_id="datalayer_list_by_type",
)
def get_objects(
    object_type: str, datalayer: DataLayer = Depends(get_actor_dl)
):
    results = datalayer.by_type(object_type)

    return results


@admin_router.delete(
    "/reset/",
    description=(
        "Resets this node by clearing the store of every actor it hosts."
    ),
    operation_id="datalayer_reset",
)
def reset_datalayer(
    actor_dls: dict[str, DataLayer] = Depends(get_hosted_actor_dls),
) -> dict:
    """Clear every hosted actor's store.

    A node-level operation: there is no single store to clear under ADR-0073,
    and demo scenarios reset a whole container between runs.  Kept off the
    actor-scoped router so that it cannot be mistaken for one actor reaching
    into another's data.

    Resetting does not *provision*.  An earlier ``init`` flag seeded the wire
    vocabulary's example actors here, which per-actor storage made unworkable in
    two independent ways: this loop iterates the actors the node already hosts,
    so on a clean node it has nothing to iterate and the seed silently never ran;
    and those example actors are named under ``https://vultron.example/users/…``,
    which is not ``{base_url}actors/{slug}`` and so can never be addressed on this
    node (ADR-0073#url-segment-computed-not-looked-up).  Provisioning an actor is ``POST /actors/``, and
    callers that need a populated node call it — see
    ``vultron.demo.utils.seed_exchange_actors``.

    The stores arrive via :func:`get_hosted_actor_dls` rather than a loop over
    ``get_datalayer``, so an app that supplied its own stores (a TestClient with
    per-actor in-memory overrides) is reset for real instead of having the
    process-global on-disk stores cleared behind it.
    """
    counts: dict[str, dict[str, int]] = {}
    for actor_id, actor_dl in actor_dls.items():
        actor_dl.clear_all()
        counts[actor_id] = actor_dl.count_all()

    return {
        "status": "datalayer reset successfully",
        "actors": len(counts),
        "n_items": counts,
    }


@router.get(
    "/{key:path}",
    description="Returns a specific object by key. Accepts any key including "
    "HTTP URL keys with percent-encoded slashes.",
    operation_id="datalayer_get_by_key",
)
def get_object_by_key(key: str, datalayer: DataLayer = Depends(get_actor_dl)):
    obj = datalayer.read(key)

    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return _serve_stored(obj)
