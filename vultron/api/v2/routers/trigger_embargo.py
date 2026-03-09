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
Trigger router for embargo-management behaviors.

Thin wrapper: validates request → calls service → returns response.
All domain logic lives in vultron.api.v2.backend.trigger_services.embargo.
"""

from fastapi import APIRouter, Depends, status

from vultron.api.v2.backend.trigger_services._models import (
    EvaluateEmbargoRequest,
    ProposeEmbargoRequest,
    TerminateEmbargoRequest,
)
from vultron.api.v2.backend.trigger_services.embargo import (
    svc_evaluate_embargo,
    svc_propose_embargo,
    svc_terminate_embargo,
)
from vultron.api.v2.datalayer.abc import DataLayer
from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

router = APIRouter(prefix="/actors", tags=["Triggers"])


@router.post(
    "/{actor_id}/trigger/propose-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger an embargo proposal.",
    description=(
        "Triggers the propose-embargo behavior for the given actor. "
        "Creates a new EmbargoEvent and emits an EmProposeEmbargo "
        "(Invite(EmbargoEvent)) activity. "
        "EM state transitions: N → P (new proposal) or A → R (revision). "
        "Returns the resulting activity in the response body (TB-04-001)."
    ),
)
def trigger_propose_embargo(
    actor_id: str,
    body: ProposeEmbargoRequest,
    dl: DataLayer = Depends(get_datalayer),
) -> dict:
    """
    Trigger the propose-embargo behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001, TB-03-002,
        TB-03-003, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return svc_propose_embargo(
        actor_id, body.case_id, body.note, body.end_time, dl
    )


@router.post(
    "/{actor_id}/trigger/evaluate-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger embargo evaluation (accept a proposal).",
    description=(
        "Triggers the evaluate-embargo behavior for the given actor. "
        "Accepts the current (or specified) embargo proposal by emitting "
        "an EmAcceptEmbargo activity. Activates the embargo on the case "
        "(EM state → ACTIVE). "
        "Returns the resulting activity in the response body (TB-04-001)."
    ),
)
def trigger_evaluate_embargo(
    actor_id: str,
    body: EvaluateEmbargoRequest,
    dl: DataLayer = Depends(get_datalayer),
) -> dict:
    """
    Trigger the evaluate-embargo (accept) behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001, TB-03-002,
        TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return svc_evaluate_embargo(actor_id, body.case_id, body.proposal_id, dl)


@router.post(
    "/{actor_id}/trigger/terminate-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger embargo termination.",
    description=(
        "Triggers the terminate-embargo behavior for the given actor. "
        "Announces the end of the active embargo by emitting an "
        "AnnounceEmbargo activity. Updates the case EM state to EXITED "
        "and clears the active embargo. "
        "Returns HTTP 409 if no active embargo exists. "
        "Returns the resulting activity in the response body (TB-04-001)."
    ),
)
def trigger_terminate_embargo(
    actor_id: str,
    body: TerminateEmbargoRequest,
    dl: DataLayer = Depends(get_datalayer),
) -> dict:
    """
    Trigger the terminate-embargo behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-002, TB-03-001, TB-03-002,
        TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return svc_terminate_embargo(actor_id, body.case_id, dl)
