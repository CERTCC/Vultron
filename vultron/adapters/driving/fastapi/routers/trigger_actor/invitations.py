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


"""Trigger routes for suggesting and inviting an actor, and for answering a
case or full-case invitation.

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
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.trigger_dispatcher import TriggerDispatcher
from vultron.core.use_cases.triggers.request_bodies import (
    AcceptCaseInviteRequest,
    FullCaseInviteReplyRequest,
    InviteActorToCaseRequest,
    RejectCaseInviteRequest,
    SuggestActorToCaseRequest,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptCaseInviteTriggerRequest,
    AcceptFullCaseInviteTriggerRequest,
    InviteActorToCaseTriggerRequest,
    RejectCaseInviteTriggerRequest,
    RejectFullCaseInviteTriggerRequest,
    SuggestActorToCaseTriggerRequest,
    TentativeRejectFullCaseInviteTriggerRequest,
)

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
    response_model=ActivityResult,
)
def trigger_suggest_actor_to_case(
    actor_id: str,
    body: SuggestActorToCaseRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the suggest-actor-to-case behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-005, TRIG-03-001, TRIG-03-002,
        TRIG-04-001, TRIG-12-001; CM-24-001
    """
    return run_trigger(
        SuggestActorToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            suggested_actor_id=body.suggested_actor_id,
            roles=body.roles,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


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
    response_model=ActivityResult,
)
def trigger_accept_case_invite(
    actor_id: str,
    body: AcceptCaseInviteRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the accept-case-invite behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-005, TRIG-03-002,
        TRIG-04-001, TRIG-12-001
    """
    return run_trigger(
        AcceptCaseInviteTriggerRequest(
            actor_id=actor_id, invite_id=body.invite_id
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/reject-case-invite",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Reject a case invitation.",
    description=(
        "Rejects an RmInviteToCaseActivity by emitting an "
        "RmRejectInviteToCaseActivity queued in the actor's outbox for "
        "delivery to the case owner."
    ),
    operation_id="actors_trigger_reject_case_invite",
    response_model=ActivityResult,
)
def trigger_reject_case_invite(
    actor_id: str,
    body: RejectCaseInviteRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the reject-case-invite behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-005, TRIG-03-002,
        TRIG-04-001, TRIG-12-001
    """
    return run_trigger(
        RejectCaseInviteTriggerRequest(
            actor_id=actor_id, invite_id=body.invite_id
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/accept-full-case-invite",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Judge the case valid: Accept(full-case Invite), RV.",
    description=(
        "Answers the CASE_MANAGER's full-case Invite with Accept, "
        "carrying this actor's own ledger position.  Fails with 409 until "
        "the actor's ledger copy has reached the Invite's position "
        "(SYNC-10-004, CM-11-012)."
    ),
    operation_id="actors_trigger_accept_full_case_invite",
    response_model=ActivityResult,
)
def trigger_accept_full_case_invite(
    actor_id: str,
    body: FullCaseInviteReplyRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the accept-full-case-invite behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-005, TRIG-03-002,
        TRIG-04-001, TRIG-12-001
    """
    return run_trigger(
        AcceptFullCaseInviteTriggerRequest(
            actor_id=actor_id, invite_id=body.invite_id
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/tentative-reject-full-case-invite",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Judge the case invalid: TentativeReject(full-case Invite), RI.",
    description=(
        "Answers the CASE_MANAGER's full-case Invite with TentativeReject, "
        "carrying this actor's own ledger position.  Fails with 409 until "
        "the actor's ledger copy has reached the Invite's position "
        "(SYNC-10-004, CM-11-012)."
    ),
    operation_id="actors_trigger_tentative_reject_full_case_invite",
    response_model=ActivityResult,
)
def trigger_tentative_reject_full_case_invite(
    actor_id: str,
    body: FullCaseInviteReplyRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the tentative-reject-full-case-invite behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-005, TRIG-03-002,
        TRIG-04-001, TRIG-12-001
    """
    return run_trigger(
        TentativeRejectFullCaseInviteTriggerRequest(
            actor_id=actor_id, invite_id=body.invite_id
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/reject-full-case-invite",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Close the case: Reject(full-case Invite), RC.",
    description=(
        "Answers the CASE_MANAGER's full-case Invite with Reject, "
        "carrying this actor's own ledger position.  Fails with 409 until "
        "the actor's ledger copy has reached the Invite's position "
        "(SYNC-10-004, CM-11-012)."
    ),
    operation_id="actors_trigger_reject_full_case_invite",
    response_model=ActivityResult,
)
def trigger_reject_full_case_invite(
    actor_id: str,
    body: FullCaseInviteReplyRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the reject-full-case-invite behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-005, TRIG-03-002,
        TRIG-04-001, TRIG-12-001
    """
    return run_trigger(
        RejectFullCaseInviteTriggerRequest(
            actor_id=actor_id, invite_id=body.invite_id
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/invite-actor-to-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Directly invite an actor to a case.",
    description=(
        "Sends the case owner's Offer of the invitee, with the offered "
        "roles, to the case's CASE_MANAGER, which emits and commits the "
        "Invite (ADR-0109).  The case must exist in the actor's DataLayer."
    ),
    operation_id="actors_trigger_invite_actor_to_case",
    response_model=ActivityResult,
)
def trigger_invite_actor_to_case(
    actor_id: str,
    body: InviteActorToCaseRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the invite-actor-to-case behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-005, TRIG-03-001, TRIG-03-002,
        TRIG-04-001, TRIG-12-001; CM-24-001
    """
    return run_trigger(
        InviteActorToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            invitee_id=body.invitee_id,
            roles=body.roles,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )
