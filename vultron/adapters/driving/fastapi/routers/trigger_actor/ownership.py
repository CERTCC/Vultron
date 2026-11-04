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


"""Trigger routes for case ownership transfer.

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
    AcceptCaseOwnershipTransferRequest,
    OfferCaseOwnershipTransferRequest,
    RejectCaseOwnershipTransferRequest,
    WithdrawCaseOwnershipTransferRequest,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptCaseOwnershipTransferTriggerRequest,
    OfferCaseOwnershipTransferTriggerRequest,
    RejectCaseOwnershipTransferTriggerRequest,
    WithdrawCaseOwnershipTransferTriggerRequest,
)

router = APIRouter(prefix="/actors", tags=["Triggers"])


@router.post(
    "/{actor_id}/trigger/offer-case-ownership-transfer",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Offer case ownership to another actor.",
    description=(
        "Emits the requesting Case Owner's proposal, an "
        "Offer(Offer(VulnerabilityCase)), to the case's CASE_MANAGER, which "
        "offers the case to the specified transferee on the owner's behalf.  "
        "The case must exist in the actor's DataLayer.  The transferee must "
        "also be known.  The returned activity is the proposal, which the "
        "withdraw trigger names (TRIG-11-001)."
    ),
    operation_id="actors_trigger_offer_case_ownership_transfer",
    response_model=ActivityResult,
)
def trigger_offer_case_ownership_transfer(
    actor_id: str,
    body: OfferCaseOwnershipTransferRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the offer-case-ownership-transfer behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-007, TRIG-03-001,
        TRIG-03-002, TRIG-04-001, TRIG-12-001; TRIG-11-001; CM-24-001
    """
    return run_trigger(
        OfferCaseOwnershipTransferTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            transferee_id=body.transferee_id,
            content=body.content,
            end_time=body.end_time,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/accept-case-ownership-transfer",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Accept a case ownership transfer offer.",
    description=(
        "Emits an Accept(Offer(VulnerabilityCase)) from the accepting actor "
        "to the case's CASE_MANAGER.  The ownership transfer offer must "
        "already exist in the actor's DataLayer (TRIG-11-002, CM-21-006)."
    ),
    operation_id="actors_trigger_accept_case_ownership_transfer",
    response_model=ActivityResult,
)
def trigger_accept_case_ownership_transfer(
    actor_id: str,
    body: AcceptCaseOwnershipTransferRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the accept-case-ownership-transfer behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-007, TRIG-03-001,
        TRIG-03-002, TRIG-04-001, TRIG-12-001; TRIG-11-002
    """
    return run_trigger(
        AcceptCaseOwnershipTransferTriggerRequest(
            actor_id=actor_id, offer_id=body.offer_id
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/reject-case-ownership-transfer",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Decline a case ownership transfer offer.",
    description=(
        "Emits a Reject(Offer(VulnerabilityCase)) from the declining actor "
        "to the case's CASE_MANAGER, which ledgers and broadcasts the "
        "decline.  The ownership transfer offer must already exist in the "
        "actor's DataLayer (TRIG-11-005, CM-21-010, CM-21-012)."
    ),
    operation_id="actors_trigger_reject_case_ownership_transfer",
    response_model=ActivityResult,
)
def trigger_reject_case_ownership_transfer(
    actor_id: str,
    body: RejectCaseOwnershipTransferRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the reject-case-ownership-transfer behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-007, TRIG-03-001,
        TRIG-03-002, TRIG-04-001, TRIG-12-001; TRIG-11-005
    """
    return run_trigger(
        RejectCaseOwnershipTransferTriggerRequest(
            actor_id=actor_id, offer_id=body.offer_id
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/withdraw-case-ownership-transfer",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Withdraw an open case ownership transfer offer.",
    description=(
        "Emits an Undo of the Case Owner's own ownership-transfer proposal "
        "to the case's CASE_MANAGER, which withdraws the offer it made from "
        "it, and ledgers and broadcasts the withdrawal, if the offer is "
        "still open.  offer_id names the proposal, which must already exist "
        "in the actor's DataLayer (TRIG-11-006, CM-21-015)."
    ),
    operation_id="actors_trigger_withdraw_case_ownership_transfer",
    response_model=ActivityResult,
)
def trigger_withdraw_case_ownership_transfer(
    actor_id: str,
    body: WithdrawCaseOwnershipTransferRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the withdraw-case-ownership-transfer behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-007, TRIG-03-001,
        TRIG-03-002, TRIG-04-001, TRIG-12-001; TRIG-11-006
    """
    return run_trigger(
        WithdrawCaseOwnershipTransferTriggerRequest(
            actor_id=actor_id, offer_id=body.offer_id
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )
