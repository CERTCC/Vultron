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

import logging
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, status

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driven.db_record import Record, record_to_object
from vultron.adapters.driving.fastapi.deps import get_actor_dl
from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.wire.as2.rehydration import rehydrate
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.collections import (
    as_OrderedCollection,
)
from vultron.wire.as2.vocab.objects.vultron_actor import (
    as_VultronApplication,
    as_VultronGroup,
    as_VultronOrganization,
    as_VultronPerson,
    as_VultronService,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

logger = logging.getLogger(__name__)

# Debug/inspection views are actor-scoped: under ADR-0071 there is no "the"
# store to inspect, and a node may host several actors (a vendor plus the
# CaseActors it self-hosts under CP-08-003).  Naming the actor in the path keeps
# ADR-0058 causal gates honest — a gate must assert that *a named actor* has
# committed some state, not merely that some actor in the container has.
router = APIRouter(prefix="/actors/{actor_id}/datalayer", tags=["datalayer"])

#: Node-level operations that legitimately span every hosted actor.  These are
#: operator actions on the process (like a restart), not one actor reading
#: another's data through the protocol.
admin_router = APIRouter(prefix="/admin/datalayer", tags=["datalayer"])


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
    obj = datalayer.read(object_id)

    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    wire_data = obj.model_dump(by_alias=True, serialize_as_any=True)
    rec = Record(
        id_=wire_data.get("id", object_id),
        type_=wire_data.get("type", ""),
        data_=wire_data,
    )
    try:
        wire_obj = record_to_object(rec)
        return AS2JSONResponse(wire_obj)
    except Exception as exc:
        logger.debug(
            "get_object: wire conversion failed for %r: %s", object_id, exc
        )
        return wire_data


@router.get(
    "/Offer/",
    response_model=as_Offer,
    operation_id="datalayer_get_offer",
)
def get_offer(
    object_id: str, datalayer: DataLayer = Depends(get_actor_dl)
) -> AS2JSONResponse:
    obj = datalayer.read(object_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return AS2JSONResponse(
        as_Offer.model_validate(
            obj.model_dump(by_alias=True, serialize_as_any=True)
        )
    )


@router.get(
    "/Report/",
    response_model=as_VulnerabilityReport,
    operation_id="datalayer_get_report",
)
def get_report(
    id: str, datalayer: DataLayer = Depends(get_actor_dl)
) -> AS2JSONResponse:
    obj = datalayer.read(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return AS2JSONResponse(
        as_VulnerabilityReport.model_validate(
            obj.model_dump(by_alias=True, serialize_as_any=True)
        )
    )


@router.get(
    "/",
    description="Returns the entire contents of the datalayer.",
    operation_id="datalayer_list",
)
def get_datalayer_contents(
    datalayer: DataLayer = Depends(get_actor_dl),
) -> AS2JSONResponse:
    data = datalayer.all()
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return AS2JSONResponse(
        {
            k: v.model_dump(mode="json", exclude_none=True, by_alias=True)
            for k, v in data.items()
        }
    )


@router.get(
    "/Offers/{offer_id}",
    response_model=as_Offer,
    description="Returns a specific object by actor id and offer id.",
    operation_id="datalayer_get_actor_offer",
)
def get_actor_offer(
    actor_id: str, offer_id: str, datalayer: DataLayer = Depends(get_actor_dl)
) -> AS2JSONResponse:
    obj = datalayer.read(offer_id)

    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    offer = as_Offer.model_validate(
        obj.model_dump(by_alias=True, serialize_as_any=True)
    )

    # Verify that the offer was targeted to the given actor
    found = False
    for _id in offer.to or []:
        if _id.endswith(actor_id):
            found = True
            break

    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return AS2JSONResponse(offer)


@router.get(
    "/Offers/",
    description="Returns all Offer objects.",
    operation_id="datalayer_list_offers",
)
def get_offers(
    datalayer: DataLayer = Depends(get_actor_dl),
) -> AS2JSONResponse:
    results = datalayer.by_type("Offer")

    return AS2JSONResponse(
        {
            k: as_Offer.model_validate(v).model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            for k, v in results.items()
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


_DATALAYER_ACTOR_TYPE_MAP: dict[str, type[as_Actor]] = {
    "Person": as_VultronPerson,
    "Organization": as_VultronOrganization,
    "Service": as_VultronService,
    "Application": as_VultronApplication,
    "Group": as_VultronGroup,
}


def _actor_class_for_payload(
    payload: dict[str, Any],
) -> type[as_Actor]:
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
    # same way ``get_actor_dl`` just did (ADR-0071) — reading the store with the
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

    outbox = as_OrderedCollection(id_=f"{canonical_id}/outbox")
    outbox.items = [
        rehydrate(activity_id, dl=datalayer) for activity_id in activity_ids
    ]

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
def reset_datalayer() -> dict:
    """Clear every hosted actor's store.

    A node-level operation: there is no single store to clear under ADR-0071,
    and demo scenarios reset a whole container between runs.  Kept off the
    actor-scoped router so that it cannot be mistaken for one actor reaching
    into another's data.

    Resetting does not *provision*.  An earlier ``init`` flag seeded the wire
    vocabulary's example actors here, which per-actor storage made unworkable in
    two independent ways: this loop iterates the actors the node already hosts,
    so on a clean node it has nothing to iterate and the seed silently never ran;
    and those example actors are named under ``https://vultron.example/users/…``,
    which is not ``{base_url}actors/{slug}`` and so can never be addressed on this
    node (ADR-0071 decision 2).  Provisioning an actor is ``POST /actors/``, and
    callers that need a populated node call it — see
    ``vultron.demo.utils.seed_exchange_actors``.
    """
    counts: dict[str, dict[str, int]] = {}
    for actor_id in actor_hosts.hosted_actor_ids():
        actor_dl = get_datalayer(actor_id)
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

    wire_data = obj.model_dump(by_alias=True, serialize_as_any=True)
    rec = Record(
        id_=wire_data.get("id", key),
        type_=wire_data.get("type", ""),
        data_=wire_data,
    )
    try:
        wire_obj = record_to_object(rec)
        return AS2JSONResponse(wire_obj)
    except Exception as exc:
        logger.debug(
            "get_object_by_key: wire conversion failed for %r: %s", key, exc
        )
        return wire_data
