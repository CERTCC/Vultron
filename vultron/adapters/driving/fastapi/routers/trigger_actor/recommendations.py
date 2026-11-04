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


"""Trigger routes for answering an actor recommendation and for offering a
participant role.

Registered on :data:`vultron.adapters.driving.fastapi.routers.trigger_actor.router`.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status

from vultron.adapters.driving.fastapi.deps import (
    get_trigger_dispatcher,
    get_trigger_dl,
)
from vultron.adapters.driving.fastapi.trigger_runner import run_trigger
from vultron.core.models.use_case_result import (
    ActivityResult,
    RoleOfferResult,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.trigger_dispatcher import TriggerDispatcher
from vultron.core.use_cases.triggers.request_bodies import (
    AcceptActorRecommendationRequest,
    OfferCaseParticipantRoleRequest,
    RejectActorRecommendationRequest,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptActorRecommendationTriggerRequest,
    OfferCaseParticipantRoleTriggerRequest,
    RejectActorRecommendationTriggerRequest,
)

router = APIRouter(prefix="/actors", tags=["Triggers"])


@router.post(
    "/{actor_id}/trigger/accept-actor-recommendation",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Accept an actor recommendation as Case Owner.",
    description=(
        "Emits an Accept(Offer(CaseParticipant)) from the Case Owner's identity "
        "addressed to the CaseActor, completing the ADR-0026 CM-16-006 approval "
        "step.  The Offer(CaseParticipant) must already exist in the actor's "
        "DataLayer (delivered by the CaseActor)."
    ),
    operation_id="actors_trigger_accept_actor_recommendation",
    response_model=ActivityResult,
)
def trigger_accept_actor_recommendation(
    actor_id: str,
    body: AcceptActorRecommendationRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the accept-actor-recommendation behavior for the given actor.

    Implements: ADR-0026 (CM-16-006); TRIG-01-001, TRIG-01-002, HTTP-03-005,
        TRIG-02-005, TRIG-03-001, TRIG-03-002, TRIG-04-001, TRIG-12-001
    """
    return run_trigger(
        AcceptActorRecommendationTriggerRequest(
            actor_id=actor_id,
            cp_offer_id=body.cp_offer_id,
            case_actor_id=body.case_actor_id,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/reject-actor-recommendation",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Reject an actor recommendation as Case Owner.",
    description=(
        "Emits a Reject(Offer(CaseParticipant)) from the Case Owner's identity "
        "addressed to the CaseActor, which ledgers it and answers the "
        "original recommender (ADR-0026, CM-16-007).  The "
        "Offer(CaseParticipant) must already exist in the actor's DataLayer "
        "(delivered by the CaseActor)."
    ),
    operation_id="actors_trigger_reject_actor_recommendation",
    response_model=ActivityResult,
)
def trigger_reject_actor_recommendation(
    actor_id: str,
    body: RejectActorRecommendationRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the reject-actor-recommendation behavior for the given actor.

    Implements: ADR-0026 (CM-16-007); TRIG-01-001, TRIG-01-002, HTTP-03-005,
        TRIG-02-005, TRIG-03-001, TRIG-03-002, TRIG-04-001, TRIG-12-001
    """
    return run_trigger(
        RejectActorRecommendationTriggerRequest(
            actor_id=actor_id,
            cp_offer_id=body.cp_offer_id,
            case_actor_id=body.case_actor_id,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/offer-case-participant-role",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Offer a CVDRole to an Actor in a case (ADR-0039).",
    description=(
        "Emits Offer(CaseParticipantRole)[context=VulnerabilityCase], whose "
        "``target`` is the actor offered the role, from the requesting "
        "actor.  This is the canonical role-delegation wire "
        "format introduced by ADR-0039, replacing the deprecated "
        "offer-case-manager-role endpoint.  The Offer is addressed to the "
        "case's CASE_MANAGER, which forwards it to the target.  The ``role`` "
        "field is required, and the CASE_MANAGER refuses an Offer of "
        "``CASE_OWNER`` or ``CASE_MANAGER`` (CM-33-003).  See SE-08-003."
    ),
    operation_id="actors_trigger_offer_case_participant_role",
    response_model=RoleOfferResult,
)
def trigger_offer_case_participant_role(
    actor_id: str,
    body: OfferCaseParticipantRoleRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> RoleOfferResult:
    """
    Trigger Offer(CaseParticipantRole) from the requesting actor (ADR-0039).

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-007, TRIG-03-001,
        TRIG-03-002, TRIG-04-001, TRIG-12-001
    """
    return run_trigger(
        OfferCaseParticipantRoleTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            target_actor_id=body.target_actor_id,
            role=body.role,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )
