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
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
    TerminateEmbargoTriggerRequest,
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
        "moves no EM state. The case owner's reject is its decision for the "
        "case, Reject(EmbargoEvent, target=Case), which rejects the proposal "
        "(EM state PROPOSED → NONE or REVISE → ACTIVE). "
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
        "Announces the end of the active embargo by emitting an "
        "AnnounceEmbargoActivity activity. Updates the case EM state to EXITED "
        "and clears the active embargo. "
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
            actor_id=actor_id, case_id=body.case_id
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )
