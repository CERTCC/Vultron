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

from copy import deepcopy

from fastapi import APIRouter, Depends, status, HTTPException

from vultron.wire.as2.rehydration import rehydrate
from vultron.core.ports.datalayer import DataLayer
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.adapters.driven.datalayer_tinydb import get_datalayer
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.collections import (
    as_OrderedCollection,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

router = APIRouter(prefix="/datalayer", tags=["datalayer"])


def _shared_dl() -> DataLayer:
    """Dependency: always returns the shared (non-actor-scoped) DataLayer.

    Prevents FastAPI from forwarding ``actor_id`` path parameters into
    ``get_datalayer(actor_id=…)`` when this function is used as a dependency.
    """
    return get_datalayer()


@router.get(
    "/{key}",
    description="Returns a specific object by key.",
    operation_id="datalayer_get_by_key",
)
def get_object_by_key(key: str, datalayer: DataLayer = Depends(get_datalayer)):
    obj = datalayer.read(key)

    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return obj


@router.get(
    "/{object_type}/{object_id}",
    description="Returns a specific object by type and ID.",
    operation_id="datalayer_get_by_type_and_id",
)
def get_object(
    object_type: str,
    object_id: str,
    datalayer: DataLayer = Depends(get_datalayer),
):
    obj = datalayer.read(object_id)

    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return obj


@router.get("/Offer/", operation_id="datalayer_get_offer")
def get_offer(
    object_id: str, datalayer: DataLayer = Depends(get_datalayer)
) -> as_Offer:
    obj = datalayer.read(object_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return as_Offer.model_validate(obj)


@router.get("/Report/", operation_id="datalayer_get_report")
def get_report(
    id: str, datalayer: DataLayer = Depends(get_datalayer)
) -> VulnerabilityReport:
    obj = datalayer.read(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return VulnerabilityReport.model_validate(obj)


@router.get(
    "/",
    description="Returns the entire contents of the datalayer.",
    operation_id="datalayer_list",
)
def get_datalayer_contents(
    datalayer: DataLayer = Depends(get_datalayer),
) -> dict[str, dict]:
    data = datalayer.all()
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return {
        k: v.model_dump(exclude_none=True, by_alias=True)
        for k, v in data.items()
    }


@router.get(
    "/Actors/{actor_id}/Offers/{offer_id}",
    description="Returns a specific object by actor id and offer id.",
    operation_id="datalayer_get_actor_offer",
)
def get_actor_offer(
    actor_id: str, offer_id: str, datalayer: DataLayer = Depends(_shared_dl)
) -> as_Offer:
    obj = datalayer.read(offer_id)

    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    offer = as_Offer.model_validate(obj)

    # Verify that the offer was targeted to the given actor
    found = False
    for _id in offer.to or []:
        if _id.endswith(actor_id):
            found = True
            break

    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return offer


@router.get(
    "/Offers/",
    description="Returns all Offer objects.",
    operation_id="datalayer_list_offers",
)
def get_offers(
    datalayer: DataLayer = Depends(get_datalayer),
) -> dict[str, as_Offer]:
    results = datalayer.by_type("Offer")

    return {k: as_Offer.model_validate(v) for k, v in results.items()}


@router.get(
    "/Reports/",
    description="Returns all VulnerabilityReport objects.",
    response_model=dict[str, VulnerabilityReport],
    operation_id="datalayer_list_reports",
)
def get_reports(
    datalayer: DataLayer = Depends(get_datalayer),
) -> dict[str, VulnerabilityReport]:
    results = datalayer.by_type("VulnerabilityReport")

    return {
        k: VulnerabilityReport.model_validate(v) for k, v in results.items()
    }


@router.get(
    "/Actors/",
    description="Returns all Actor objects.",
    operation_id="datalayer_list_actors",
)
def get_actors(
    datalayer: DataLayer = Depends(get_datalayer),
) -> dict[str, as_Actor]:
    results = datalayer.by_type("Actor")

    return {k: as_Actor.model_validate(v) for k, v in results.items()}


@router.get(
    "/Actors/{actor_id}/outbox/",
    description="Returns the outbox of a specific Actor.",
    response_model=as_OrderedCollection,
    operation_id="datalayer_get_actor_outbox",
)
def get_actor_outbox(
    actor_id: str, datalayer: DataLayer = Depends(_shared_dl)
) -> as_OrderedCollection:
    actor_obj = datalayer.read(actor_id)

    if not actor_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    actor = as_Actor.model_validate(actor_obj)

    if not actor.outbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # make a copy
    outbox = deepcopy(actor.outbox)

    outbox.items = [
        rehydrate(item, dl=datalayer)
        for item in outbox.items
        if isinstance(item, str) or isinstance(item, as_Object)
    ]

    return outbox


@router.get(
    "/{object_type}s/",
    description="Returns all objects of a given type.",
    operation_id="datalayer_list_by_type",
)
def get_objects(
    object_type: str, datalayer: DataLayer = Depends(get_datalayer)
):
    results = datalayer.by_type(object_type)

    return results


@router.delete(
    "/reset/",
    description="Resets the datalayer by clearing all stored objects.",
    operation_id="datalayer_reset",
)
def reset_datalayer(
    init: bool = False, datalayer: DataLayer = Depends(get_datalayer)
) -> dict:
    """Resets the datalayer by clearing all stored objects."""
    datalayer.clear_all()
    if init:
        from vultron.wire.as2.vocab.examples._base import initialize_examples

        initialize_examples(datalayer=datalayer)

    return {
        "status": "datalayer reset successfully",
        "n_items": datalayer.count_all(),
    }
