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
from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from vultron.adapters.driven.datalayer import get_shared_dl
from vultron.adapters.driven.db_record import Record, record_to_object
from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.core.ports.datalayer import DataLayer
from vultron.wire.as2.rehydration import rehydrate
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.base import as_Object
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

router = APIRouter(prefix="/datalayer", tags=["datalayer"])


@router.get(
    "/{object_type}/{object_id}",
    description="Returns a specific object by type and ID.",
    operation_id="datalayer_get_by_type_and_id",
)
def get_object(
    object_type: str,
    object_id: str,
    datalayer: DataLayer = Depends(get_shared_dl),
):
    obj = datalayer.read(object_id)

    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return obj


@router.get(
    "/Offer/",
    response_model=as_Offer,
    operation_id="datalayer_get_offer",
)
def get_offer(
    object_id: str, datalayer: DataLayer = Depends(get_shared_dl)
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
    id: str, datalayer: DataLayer = Depends(get_shared_dl)
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
    datalayer: DataLayer = Depends(get_shared_dl),
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
    "/Actors/{actor_id}/Offers/{offer_id}",
    response_model=as_Offer,
    description="Returns a specific object by actor id and offer id.",
    operation_id="datalayer_get_actor_offer",
)
def get_actor_offer(
    actor_id: str, offer_id: str, datalayer: DataLayer = Depends(get_shared_dl)
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
    datalayer: DataLayer = Depends(get_shared_dl),
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
    datalayer: DataLayer = Depends(get_shared_dl),
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
    datalayer: DataLayer = Depends(get_shared_dl),
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
    "/Actors/{actor_id}/outbox/",
    description="Returns the outbox of a specific Actor.",
    response_model=as_OrderedCollection,
    operation_id="datalayer_get_actor_outbox",
)
def get_actor_outbox(
    actor_id: str, datalayer: DataLayer = Depends(get_shared_dl)
) -> AS2JSONResponse:
    actor_obj = datalayer.read(actor_id)

    if not actor_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    actor = as_Actor.model_validate(
        actor_obj.model_dump(by_alias=True, serialize_as_any=True)
    )

    if not actor.outbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # make a copy
    outbox = deepcopy(actor.outbox)

    outbox.items = [
        rehydrate(item, dl=datalayer)
        for item in outbox.items
        if isinstance(item, str) or isinstance(item, as_Object)
    ]

    return AS2JSONResponse(outbox)


@router.get(
    "/{object_type}s/",
    description="Returns all objects of a given type.",
    operation_id="datalayer_list_by_type",
)
def get_objects(
    object_type: str, datalayer: DataLayer = Depends(get_shared_dl)
):
    results = datalayer.by_type(object_type)

    return results


@router.delete(
    "/reset/",
    description="Resets the datalayer by clearing all stored objects.",
    operation_id="datalayer_reset",
)
def reset_datalayer(
    init: bool = False, datalayer: DataLayer = Depends(get_shared_dl)
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


@router.get(
    "/{key:path}",
    description="Returns a specific object by key. Accepts any key including "
    "HTTP URL keys with percent-encoded slashes.",
    operation_id="datalayer_get_by_key",
)
def get_object_by_key(key: str, datalayer: DataLayer = Depends(get_shared_dl)):
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
