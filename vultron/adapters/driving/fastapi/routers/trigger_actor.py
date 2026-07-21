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
Trigger router for actor-level participant behaviors.

Thin wrapper: validates request → calls adapter → returns response.
All domain logic lives in vultron.core.use_cases.triggers.actor.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status

from vultron.adapters.driving.fastapi.deps import (
    get_canonical_actor_dl,
    get_trigger_dl,
    get_trigger_service,
)
from vultron.adapters.driving.fastapi.errors import domain_error_translation
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.adapters.driving.fastapi.trigger_models import (
    AcceptActorRecommendationRequest,
    AcceptCaseInviteRequest,
    InviteActorToCaseRequest,
    OfferCaseManagerRoleRequest,
    SuggestActorToCaseRequest,
)
from vultron.core.ports.datalayer import ActorScopedDataLayer, DataLayer
from vultron.core.ports.trigger_service import TriggerServicePort

router = APIRouter(prefix="/actors", tags=["Triggers"])


@router.post(
    "/{actor_id}/trigger/suggest-actor-to-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Suggest another actor for a case.",
    description=(
        "Emits a RecommendActorActivity addressed to the case owner "
        "(typically the CaseActor).  The CaseActor then autonomously "
        "invites the suggested actor via RmInviteToCaseActivity."
    ),
    operation_id="actors_trigger_suggest_actor_to_case",
)
def trigger_suggest_actor_to_case(
    actor_id: str,
    body: SuggestActorToCaseRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    dl: DataLayer = Depends(get_trigger_dl),
    actor_dl: ActorScopedDataLayer = Depends(get_canonical_actor_dl),
) -> dict:
    """
    Trigger the suggest-actor-to-case behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-04-001
    """
    with domain_error_translation():
        result = svc.suggest_actor_to_case(
            actor_id=actor_id,
            case_id=body.case_id,
            suggested_actor_id=body.suggested_actor_id,
        )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result


@router.post(
    "/{actor_id}/trigger/accept-case-invite",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Accept a case invitation.",
    description=(
        "Accepts an RmInviteToCaseActivity by emitting an "
        "RmAcceptInviteToCaseActivity queued in the actor's outbox for "
        "delivery to the case owner."
    ),
    operation_id="actors_trigger_accept_case_invite",
)
def trigger_accept_case_invite(
    actor_id: str,
    body: AcceptCaseInviteRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    dl: DataLayer = Depends(get_trigger_dl),
    actor_dl: ActorScopedDataLayer = Depends(get_canonical_actor_dl),
) -> dict:
    """
    Trigger the accept-case-invite behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-04-001
    """
    with domain_error_translation():
        result = svc.accept_case_invite(
            actor_id=actor_id,
            invite_id=body.invite_id,
        )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result


@router.post(
    "/{actor_id}/trigger/invite-actor-to-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Directly invite an actor to a case.",
    description=(
        "Emits an RmInviteToCaseActivity from the case owner to the "
        "specified invitee.  The case must exist in the actor's DataLayer."
    ),
    operation_id="actors_trigger_invite_actor_to_case",
)
def trigger_invite_actor_to_case(
    actor_id: str,
    body: InviteActorToCaseRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    dl: DataLayer = Depends(get_trigger_dl),
    actor_dl: ActorScopedDataLayer = Depends(get_canonical_actor_dl),
) -> dict:
    """
    Trigger the invite-actor-to-case behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-04-001
    """
    with domain_error_translation():
        result = svc.invite_actor_to_case(
            actor_id=actor_id,
            case_id=body.case_id,
            invitee_id=body.invitee_id,
            roles=body.roles,
        )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result


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
)
def trigger_accept_actor_recommendation(
    actor_id: str,
    body: AcceptActorRecommendationRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    dl: DataLayer = Depends(get_trigger_dl),
    actor_dl: ActorScopedDataLayer = Depends(get_canonical_actor_dl),
) -> dict:
    """
    Trigger the accept-actor-recommendation behavior for the given actor.

    Implements: ADR-0026 (CM-16-006); TB-01-001, TB-01-002, TB-01-003,
        TB-02-001, TB-03-001, TB-03-002, TB-04-001
    """
    with domain_error_translation():
        result = svc.accept_actor_recommendation(
            actor_id=actor_id,
            cp_offer_id=body.cp_offer_id,
            case_actor_id=body.case_actor_id,
        )
    background_tasks.add_task(outbox_handler, actor_id, actor_dl, dl)
    return result


@router.post(
    "/{actor_id}/trigger/offer-case-manager-role",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Offer the CASE_MANAGER role to the Case Actor.",
    description=(
        "Emits an Offer(CaseManagerRole) from the Case Actor's identity to "
        "itself, initiating the CASE_MANAGER delegation handshake.  The Case "
        "Actor must already exist in the DataLayer.  This is the trigger-side "
        "path for DEMOMA-08-007; the auto-accept is handled by "
        "OfferCaseManagerRoleReceivedUseCase on the Case Actor's inbox side."
    ),
    operation_id="actors_trigger_offer_case_manager_role",
)
def trigger_offer_case_manager_role(
    actor_id: str,
    body: OfferCaseManagerRoleRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    dl: DataLayer = Depends(get_trigger_dl),
) -> dict:
    """
    Trigger the offer-case-manager-role behavior for the given actor.

    The BT runs under the Case Actor's identity (PCR-08-007), so the Offer
    activity is queued in the **Case Actor's** outbox — not the path actor's.
    ``outbox_handler`` is therefore scheduled against the Case Actor's
    actor-scoped DataLayer, resolved from the use-case result's
    ``emitting_actor_id`` field.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-04-001; DEMOMA-08-007
    """
    with domain_error_translation():
        result = svc.offer_case_manager_role(
            actor_id=actor_id,
            case_id=body.case_id,
        )
    emitting_actor_id = result.get("emitting_actor_id", actor_id)
    emitting_dl = dl.clone_for_actor(emitting_actor_id)
    background_tasks.add_task(
        outbox_handler, emitting_actor_id, emitting_dl, dl
    )
    return result
