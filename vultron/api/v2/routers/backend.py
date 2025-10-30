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
from fastapi import APIRouter, status, Response, Depends

from vultron.api.data import DataLayer, get_datalayer
from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport

router = APIRouter(prefix="/datalayer", tags=["datalayer"])


@router.get(
    "/offers",
    response_model=list[as_Offer],
    response_model_exclude_none=True,
    description="Get all Offer objects. (scoped to the actor) (This is a stub implementation.)",
)
def get_offers(
    datalayer: DataLayer = Depends(get_datalayer),
) -> list[as_Offer]:
    """Returns a list of all Offer objects."""
    return datalayer.get_all_offers()


@router.post(
    "/offers",
    description="Create a new Offer object. (This is a stub implementation.)",
    response_model=as_Offer,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def add_offer(
    offer: as_Offer,
    response: Response,
    datalayer: DataLayer = Depends(get_datalayer),
) -> as_Offer:
    """Creates an Offer object."""
    datalayer.receive_offer(offer)

    response.headers["Location"] = f"/offers/{offer.as_id}"

    return offer


@router.get(
    "/reports",
    response_model=list[VulnerabilityReport],
    response_model_exclude_none=True,
    description="Get all Report objects. (scoped to the actor) (This is a stub implementation.)",
)
def get_reports(
    datalayer: DataLayer = Depends(get_datalayer),
) -> list[VulnerabilityReport]:
    """Returns a list of all Report objects."""
    return datalayer.get_all_reports()


@router.post(
    "/reports",
    description="Create a new Report object. (This is a stub implementation.)",
    response_model=VulnerabilityReport,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_report(
    report: VulnerabilityReport,
    response: Response,
    datalayer: DataLayer = Depends(get_datalayer),
) -> VulnerabilityReport:
    """Creates a Report object."""
    datalayer.receive_report(report)

    response.headers["Location"] = f"/reports/{report.as_id}"

    return report


def main():
    pass


if __name__ == "__main__":
    main()
