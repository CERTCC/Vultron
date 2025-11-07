#!/usr/bin/env python

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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

from fastapi import APIRouter, status, HTTPException

from vultron.api.v2.data.store import get_datalayer
from vultron.as_vocab.base.base import as_Base
from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.scripts import vocab_examples

router = APIRouter(prefix="/datalayer", tags=["datalayer"])


@router.get("/{key}", description="Returns a specific object by key.")
def get_object_by_key(key: str) -> as_Base:
    datalayer = get_datalayer()

    obj = datalayer.read(key)

    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return obj


@router.get(
    "/{object_type}/{object_id}",
    description="Returns a specific object by type and ID.",
)
def get_object(object_type: str, object_id: str) -> as_Base:
    datalayer = get_datalayer()

    obj = datalayer.read(object_id)

    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return obj


@router.get("/Offer/")
def get_offer(object_id: str) -> as_Offer:
    return as_Offer.model_validate(
        get_object(object_type="Offer", object_id=object_id)
    )


@router.get("/Report/")
def get_report(id: str) -> VulnerabilityReport:
    return VulnerabilityReport.model_validate(
        get_object(object_type="VulnerabilityReport", object_id=id)
    )


@router.get("/", description="Returns the entire contents of the datalayer.")
def get_datalayer_contents() -> dict[str, dict]:
    datalayer = get_datalayer()
    data = datalayer.all()

    data = {
        k: v.model_dump(exclude_none=True, by_alias=True)
        for k, v in data.items()
    }

    return data


@router.get("/Offers/", description="Returns all Offer objects.")
def get_offers() -> dict[str, as_Offer]:
    datalayer = get_datalayer()

    results = datalayer.by_type("Offer")

    return {k: as_Offer.model_validate(v) for k, v in results.items()}


@router.get(
    "/Reports/", description="Returns all VulnerabilityReport objects."
)
def get_reports() -> dict[str, VulnerabilityReport]:
    datalayer = get_datalayer()

    results = datalayer.by_type("VulnerabilityReport")

    return {
        k: VulnerabilityReport.model_validate(v) for k, v in results.items()
    }


@router.get("/Actors/", description="Returns all Actor objects.")
def get_actors() -> dict[str, as_Actor]:
    datalayer = get_datalayer()

    results = datalayer.by_type("Actor")

    return {k: as_Actor.model_validate(v) for k, v in results.items()}


@router.post("/reset")
def reset_datalayer() -> dict:
    """Resets the datalayer by clearing all stored objects."""

    datalayer = get_datalayer()
    datalayer.clear()
    vocab_examples.initialize_examples()
    return {
        "status": "datalayer reset successfully",
        "n_items": len(datalayer.all()),
    }


@router.get(
    "/{object_type}s/", description="Returns all objects of a given type."
)
def get_objects(object_type: str) -> dict[str, as_Base]:
    datalayer = get_datalayer()

    results = datalayer.by_type(object_type)

    return results
