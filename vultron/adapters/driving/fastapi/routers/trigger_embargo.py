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

Thin wrapper: validates the HTTP body, builds the verb's core request and hands
it to :func:`~vultron.adapters.driving.fastapi.trigger_runner.run_trigger`.
All domain logic lives in vultron.core.use_cases.triggers.embargo.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status

from vultron.adapters.driving.fastapi.deps import (
    get_trigger_dispatcher,
    get_trigger_dl,
)
from vultron.adapters.driving.fastapi.trigger_runner import run_trigger
from vultron.core.models.use_case_result import ActivityResult
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.trigger_dispatcher import TriggerDispatcher
from vultron.core.use_cases.triggers.request_bodies import (
    AcceptEmbargoRequest,
    ProposeEmbargoRequest,
    ProposeEmbargoRevisionRequest,
    RejectEmbargoRequest,
    TerminateEmbargoRequest,
    WithdrawEmbargoRequest,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
    TerminateEmbargoTriggerRequest,
    WithdrawEmbargoTriggerRequest,
)

router = APIRouter(prefix="/actors", tags=["Triggers"])


@router.post(
    "/{actor_id}/trigger/propose-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger an embargo proposal.",
    description=(
        "Triggers the propose-embargo behavior for the given actor. "
        "Creates a new EmbargoEvent and emits an EmProposeEmbargoActivity "
        "(Invite(EmbargoEvent)) activity. "
        "EM state transitions: N → P (new proposal) or A → R (revision). "
        "Returns the resulting activity in the response body (TRIG-04-001)."
    ),
    operation_id="actors_trigger_propose_embargo",
    response_model=ActivityResult,
)
def trigger_propose_embargo(
    actor_id: str,
    body: ProposeEmbargoRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the propose-embargo behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-002, TRIG-03-001, TRIG-03-002,
        TRIG-03-003, TRIG-04-001, TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001
    """
    return run_trigger(
        ProposeEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            end_time=body.end_time,
            note=body.note,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/accept-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger embargo acceptance (accept a proposal).",
    description=(
        "Triggers the accept-embargo behavior for the given actor. "
        "A participant accepts the current (or specified) embargo proposal "
        "with Accept(Invite(EmbargoEvent)), which records its own consent and "
        "moves no EM state. The case owner's accept is its decision for the "
        "case, Accept(EmbargoEvent, target=Case), which activates the "
        "embargo (EM state → ACTIVE). "
        "Returns the resulting activity in the response body (TRIG-04-001)."
    ),
    operation_id="actors_trigger_accept_embargo",
    response_model=ActivityResult,
)
def trigger_accept_embargo(
    actor_id: str,
    body: AcceptEmbargoRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the accept-embargo behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-002, TRIG-03-001, TRIG-03-002,
        TRIG-04-001, TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001
    """
    return run_trigger(
        AcceptEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            proposal_id=body.proposal_id,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/reject-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger embargo rejection (reject a proposal).",
    description=(
        "Triggers the reject-embargo behavior for the given actor. "
        "A participant rejects the current (or specified) embargo proposal "
        "with Reject(Invite(EmbargoEvent)), which records its own refusal and "
        "moves no EM state. A CASE_MANAGER that is not the owner records its "
        "own refusal as its Update(EmbargoConsent) of its row instead, and "
        "sends no Reject: the CASE_MANAGER's Reject of a proposal is its "
        "abandonment of it (MSM-07-004). The case owner's reject is its "
        "decision for the case, Reject(EmbargoEvent, target=Case), which "
        "rejects the proposal "
        "(EM state PROPOSED → NONE or REVISE → ACTIVE, or unchanged while "
        "another proposal is open). "
        "When the owner is also the CASE_MANAGER and rejects the last open "
        "revision while CS is public, exploited, or attacked, the rejection "
        "also terminates the embargo in the same act (EM → EXITED), committed "
        "as the Reject entry followed by the owner's ET Remove(EmbargoEvent) "
        "entry; a refused termination commits neither (MSM-07-009, EMB-04-002). "
        "Returns the resulting activity in the response body (TRIG-04-001)."
    ),
    operation_id="actors_trigger_reject_embargo",
    response_model=ActivityResult,
)
def trigger_reject_embargo(
    actor_id: str,
    body: RejectEmbargoRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the reject-embargo behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-002, TRIG-03-001, TRIG-03-002,
        TRIG-04-001, TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001
    """
    return run_trigger(
        RejectEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            proposal_id=body.proposal_id,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/propose-embargo-revision",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger an embargo revision proposal.",
    description=(
        "Triggers the propose-embargo-revision behavior for the given actor. "
        "Proposes a revision to the active embargo by emitting an "
        "EmProposeEmbargoActivity activity. "
        "Only valid when EM state is ACTIVE or REVISE; "
        "use propose-embargo for initial proposals. "
        "EM state transitions: ACTIVE → REVISE or REVISE → REVISE. "
        "Returns the resulting activity in the response body (TRIG-04-001)."
    ),
    operation_id="actors_trigger_propose_embargo_revision",
    response_model=ActivityResult,
)
def trigger_propose_embargo_revision(
    actor_id: str,
    body: ProposeEmbargoRevisionRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the propose-embargo-revision behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-002, TRIG-03-001, TRIG-03-002,
        TRIG-03-003, TRIG-04-001, TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001
    """
    return run_trigger(
        ProposeEmbargoRevisionTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            end_time=body.end_time,
            note=body.note,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/terminate-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger embargo termination.",
    description=(
        "Triggers the terminate-embargo behavior for the given actor. "
        "Ends the active embargo with a Remove(EmbargoEvent) activity. "
        "Updates the case EM state to EXITED and clears the active embargo. "
        "An EARLY request may name its cause (FIX_READY with its vendors, "
        "FIX_DEPLOYED or OTHER); one that names none is recorded as OTHER. "
        "A THREAT_SIGNAL cause, or any cause on END_TIME_REACHED, is refused "
        "with HTTP 422 (EMB-13-004, EMB-13-005). "
        "Returns HTTP 409 if no active embargo exists. "
        "Returns the resulting activity in the response body (TRIG-04-001)."
    ),
    operation_id="actors_trigger_terminate_embargo",
    response_model=ActivityResult,
)
def trigger_terminate_embargo(
    actor_id: str,
    body: TerminateEmbargoRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the terminate-embargo behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-002, TRIG-03-001, TRIG-03-002,
        TRIG-04-001, TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001
    """
    return run_trigger(
        TerminateEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            reason=body.reason,
            cause=body.cause,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/withdraw-embargo",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger withdrawal from the embargo in force.",
    description=(
        "Triggers the withdraw-embargo behavior for the given actor. "
        "A participant whose consent to the active embargo is AGREED leaves "
        "it by sending Leave(EmbargoEvent) to the CASE_MANAGER; no Invite is "
        "named. The participant's consent to the embargo in force, and to "
        "any open revision it agreed to, becomes DECLINED; the embargo stays "
        "in force for everyone else and the case's EM state does not move "
        "(EP-09-013, MSM-07-010). "
        "Returns HTTP 409 when no embargo is in force, when the actor's "
        "consent to it is not AGREED, or when the actor is the case owner, "
        "which ends an embargo with terminate-embargo instead. "
        "Returns HTTP 404 when the actor holds no participant record on the "
        "case. "
        "Returns the resulting activity in the response body (TRIG-04-001)."
    ),
    operation_id="actors_trigger_withdraw_embargo",
    response_model=ActivityResult,
)
def trigger_withdraw_embargo(
    actor_id: str,
    body: WithdrawEmbargoRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the withdraw-embargo behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-002, TRIG-03-001, TRIG-03-002,
        TRIG-04-001, TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001, EP-09-013
    """
    return run_trigger(
        WithdrawEmbargoTriggerRequest(actor_id=actor_id, case_id=body.case_id),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )
