#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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

"""
Trigger router for case-management behaviors.

Thin wrapper: validates request → calls service → returns response.
All domain logic lives in vultron.api.v2.backend.trigger_services.case.
"""

from fastapi import APIRouter, Depends, status

from vultron.api.v2.backend.trigger_services._models import CaseTriggerRequest
from vultron.api.v2.backend.trigger_services.case import (
    defer_case_trigger,
    engage_case_trigger,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.adapters.driven.datalayer_tinydb import get_datalayer

router = APIRouter(prefix="/actors", tags=["Triggers"])


@router.post(
    "/{actor_id}/trigger/engage-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger case engagement.",
    description=(
        "Triggers the engage-case behavior for the given actor. "
        "Emits a Join(VulnerabilityCase) activity (RmEngageCaseActivity), "
        "transitions the actor's RM state to ACCEPTED in the case, "
        "and returns the activity in the response body (TB-04-001)."
    ),
)
def trigger_engage_case(
    actor_id: str,
    body: CaseTriggerRequest,
    dl: DataLayer = Depends(get_datalayer),
) -> dict:
    """
    Trigger the engage-case behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return engage_case_trigger(actor_id, body.case_id, dl)


@router.post(
    "/{actor_id}/trigger/defer-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger case deferral.",
    description=(
        "Triggers the defer-case behavior for the given actor. "
        "Emits an Ignore(VulnerabilityCase) activity (RmDeferCaseActivity), "
        "transitions the actor's RM state to DEFERRED in the case, "
        "and returns the activity in the response body (TB-04-001)."
    ),
)
def trigger_defer_case(
    actor_id: str,
    body: CaseTriggerRequest,
    dl: DataLayer = Depends(get_datalayer),
) -> dict:
    """
    Trigger the defer-case behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return defer_case_trigger(actor_id, body.case_id, dl)
