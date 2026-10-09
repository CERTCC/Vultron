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
Trigger router for report-management behaviors.

Thin wrapper: validates the HTTP body, builds the verb's core request and hands
it to :func:`~vultron.adapters.driving.fastapi.trigger_runner.run_trigger`.
All domain logic lives in vultron.core.use_cases.triggers.report.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status

from vultron.adapters.driving.fastapi.deps import (
    get_trigger_dispatcher,
    get_trigger_dl,
)
from vultron.adapters.driving.fastapi.trigger_runner import run_trigger
from vultron.core.models.use_case_result import ActivityResult, OfferResult
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.trigger_dispatcher import TriggerDispatcher
from vultron.core.use_cases.triggers.request_bodies import (
    CloseReportRequest,
    InvalidateReportRequest,
    RejectReportRequest,
    SubmitReportRequest,
    ValidateReportRequest,
)
from vultron.core.use_cases.triggers.requests import (
    CloseReportTriggerRequest,
    InvalidateReportTriggerRequest,
    RejectReportTriggerRequest,
    SubmitReportTriggerRequest,
    ValidateReportTriggerRequest,
)

router = APIRouter(prefix="/actors", tags=["Triggers"])


@router.post(
    "/{actor_id}/trigger/validate-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger report validation.",
    description=(
        "Triggers the validate-report behavior for the given actor. "
        "Invokes the ValidateReportBT tree via the bridge layer and "
        "returns the resulting ActivityStreams activity (TRIG-04-001)."
    ),
    operation_id="actors_trigger_validate_report",
    response_model=ActivityResult,
)
def trigger_validate_report(
    actor_id: str,
    body: ValidateReportRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the validate-report behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-001, TRIG-03-001,
        TRIG-03-002, TRIG-03-003, TRIG-04-001, TRIG-05-001, TRIG-05-002,
        TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001
    """
    return run_trigger(
        ValidateReportTriggerRequest(
            actor_id=actor_id, offer_id=body.offer_id, note=body.note
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/invalidate-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger report invalidation.",
    description=(
        "Triggers the invalidate-report behavior for the given actor. "
        "Emits a TentativeReject(Offer(VulnerabilityReport)) activity "
        "(RmInvalidateReportActivity) and returns it in the response body (TRIG-04-001). "
        "Persists a ParticipantStatus record with RM.INVALID for the actor "
        "and report."
    ),
    operation_id="actors_trigger_invalidate_report",
    response_model=ActivityResult,
)
def trigger_invalidate_report(
    actor_id: str,
    body: InvalidateReportRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the invalidate-report behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-001, TRIG-03-001, TRIG-03-002,
        TRIG-03-003, TRIG-04-001, TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001
    """
    return run_trigger(
        InvalidateReportTriggerRequest(
            actor_id=actor_id, offer_id=body.offer_id, note=body.note
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/reject-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger hard-close of a report.",
    description=(
        "Triggers the reject-report behavior for the given actor. "
        "Emits a Reject(Offer(VulnerabilityReport)) activity (RmCloseReportActivity) "
        "and returns it in the response body (TRIG-04-001). "
        "A non-empty note is required (TRIG-03-004). "
        "Persists a ParticipantStatus record with RM.CLOSED for the actor "
        "and report. "
        "Returns HTTP 409 if the report's RM state has no close edge "
        "(e.g. VALID; VP-02-004): nothing is emitted."
    ),
    operation_id="actors_trigger_reject_report",
    response_model=ActivityResult,
)
def trigger_reject_report(
    actor_id: str,
    body: RejectReportRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the reject-report (hard-close) behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-001, TRIG-03-001, TRIG-03-002,
        TRIG-03-004, TRIG-04-001, TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001
    """
    # The body requires the ``note`` key (TRIG-03-004) but tolerates an empty
    # string with a warning; the core request takes ``None`` for "no reason".
    return run_trigger(
        RejectReportTriggerRequest(
            actor_id=actor_id, offer_id=body.offer_id, note=body.note or None
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/close-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger RM lifecycle closure of a report.",
    description=(
        "Triggers the close-report behavior for the given actor. "
        "Emits a Reject(Offer(VulnerabilityReport)) activity (RmCloseReportActivity) "
        "representing the RM → C (CLOSED) transition, and returns it in the "
        "response body (TRIG-04-001). "
        "Persists a ParticipantStatus record with RM.CLOSED for the actor "
        "and report. "
        "Unlike reject-report (a hard-reject, which also accepts a repeat "
        "close as a confirmation), this endpoint closes a report that has "
        "progressed through the RM lifecycle. Returns HTTP 409 if the report "
        "is already CLOSED, or if its RM state has no close edge (e.g. VALID; "
        "VP-02-004)."
    ),
    operation_id="actors_trigger_close_report",
    response_model=ActivityResult,
)
def trigger_close_report(
    actor_id: str,
    body: CloseReportRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the close-report (RM → CLOSED) behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-001, TRIG-03-001, TRIG-03-002,
        TRIG-03-003, TRIG-04-001, TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001
    """
    return run_trigger(
        CloseReportTriggerRequest(
            actor_id=actor_id, offer_id=body.offer_id, note=body.note
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/submit-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create and offer a vulnerability report.",
    description=(
        "Creates a VulnerabilityReport in the actor's DataLayer and queues an "
        "RmSubmitReportActivity (Offer) to the specified recipient. "
        "An optional proposed_embargo_end_time states the Reporter's embargo "
        "terms for the report; the Offer then carries them as "
        "proposedEmbargo (EP-04-004). "
        "Returns the serialised offer so the caller can deliver it to the "
        "recipient's inbox."
    ),
    operation_id="actors_trigger_submit_report",
    response_model=OfferResult,
)
def trigger_submit_report(
    actor_id: str,
    body: SubmitReportRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> OfferResult:
    """
    Create a VulnerabilityReport and offer it to a recipient.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-001, TRIG-03-002,
        TRIG-04-001, TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001
    """
    return run_trigger(
        SubmitReportTriggerRequest(
            actor_id=actor_id,
            report_name=body.report_name,
            report_content=body.report_content,
            recipient_id=body.recipient_id,
            proposed_embargo_end_time=body.proposed_embargo_end_time,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )
