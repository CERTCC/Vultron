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

Thin wrapper: validates the HTTP body, builds the verb's core request and hands
it to :func:`~vultron.adapters.driving.fastapi.trigger_runner.run_trigger`.
All domain logic lives in vultron.core.use_cases.triggers.case.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status

from vultron.adapters.driving.fastapi.deps import (
    get_trigger_dispatcher,
    get_trigger_dl,
)
from vultron.adapters.driving.fastapi.trigger_runner import run_trigger
from vultron.core.models.use_case_result import (
    ActivityResult,
    CaseResult,
    StatusResult,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.trigger_dispatcher import TriggerDispatcher
from vultron.core.use_cases.triggers.request_bodies import (
    AddObjectToCaseRequest,
    AddOnBehalfStatusRequest,
    AddReportToCaseRequest,
    CaseTriggerRequest,
    CreateCaseRequest,
)
from vultron.core.use_cases.triggers.requests import (
    AddObjectToCaseTriggerRequest,
    AddOnBehalfStatusTriggerRequest,
    AddReportToCaseTriggerRequest,
    CreateCaseTriggerRequest,
    DeferCaseTriggerRequest,
    EngageCaseTriggerRequest,
)

router = APIRouter(prefix="/actors", tags=["Triggers"])


@router.post(
    "/{actor_id}/trigger/engage-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger case engagement.",
    description=(
        "Triggers the engage-case behavior for the given actor. "
        "Emits a Join(VulnerabilityCase) activity (RmEngageCaseActivity), "
        "transitions the actor's RM state to ACCEPTED in the case, "
        "and returns the activity in the response body (TRIG-04-001)."
    ),
    operation_id="actors_trigger_engage_case",
    response_model=ActivityResult,
)
def trigger_engage_case(
    actor_id: str,
    body: CaseTriggerRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the engage-case behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-004, TRIG-03-001, TRIG-03-002,
        TRIG-04-001, TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001
    """
    return run_trigger(
        EngageCaseTriggerRequest(actor_id=actor_id, case_id=body.case_id),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/defer-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger case deferral.",
    description=(
        "Triggers the defer-case behavior for the given actor. "
        "Emits an Ignore(VulnerabilityCase) activity (RmDeferCaseActivity), "
        "transitions the actor's RM state to DEFERRED in the case, "
        "and returns the activity in the response body (TRIG-04-001)."
    ),
    operation_id="actors_trigger_defer_case",
    response_model=ActivityResult,
)
def trigger_defer_case(
    actor_id: str,
    body: CaseTriggerRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the defer-case behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-004, TRIG-03-001, TRIG-03-002,
        TRIG-04-001, TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001
    """
    return run_trigger(
        DeferCaseTriggerRequest(actor_id=actor_id, case_id=body.case_id),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/add-object-to-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Add an existing AS2 object to a case.",
    description=(
        "Adds any existing AS2 object (identified by ``object_id``) to a "
        "VulnerabilityCase and queues an Add(object, target=case) activity "
        "in the actor's outbox for delivery to case participants. "
        "The object must already exist in the actor's datalayer. "
        "Type-specific convenience triggers (e.g., ``add-report-to-case``) "
        "delegate here after performing type validation (TRIG-10-001)."
    ),
    operation_id="actors_trigger_add_object_to_case",
    response_model=ActivityResult,
)
def trigger_add_object_to_case(
    actor_id: str,
    body: AddObjectToCaseRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """Add an existing AS2 object to a case.

    Implements:
        TRIG-10-001, TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-004,
        TRIG-03-001, TRIG-03-002, TRIG-04-001, TRIG-06-001, TRIG-06-002,
        TRIG-12-001
    """
    return run_trigger(
        AddObjectToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            object_id=body.object_id,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/create-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a new VulnerabilityCase.",
    description=(
        "Creates a local VulnerabilityCase attributed to the actor and "
        "queues a CreateCaseActivity in the actor's outbox for delivery "
        "to the CaseActor.  An optional report_id links an existing "
        "VulnerabilityReport to the new case."
    ),
    operation_id="actors_trigger_create_case",
    response_model=CaseResult,
)
def trigger_create_case(
    actor_id: str,
    body: CreateCaseRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> CaseResult:
    """
    Trigger the create-case behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-004, TRIG-03-001, TRIG-03-002,
        TRIG-04-001, TRIG-12-001
    """
    return run_trigger(
        CreateCaseTriggerRequest(
            actor_id=actor_id,
            name=body.name,
            content=body.content,
            report_id=body.report_id,
            to=body.to,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/add-report-to-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Add a report to an existing case.",
    description=(
        "Links a VulnerabilityReport to an existing VulnerabilityCase and "
        "queues an AddReportToCaseActivity in the actor's outbox."
    ),
    operation_id="actors_trigger_add_report_to_case",
    response_model=ActivityResult,
)
def trigger_add_report_to_case(
    actor_id: str,
    body: AddReportToCaseRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> ActivityResult:
    """
    Trigger the add-report-to-case behavior for the given actor.

    Implements:
        TRIG-01-001, TRIG-01-002, HTTP-03-005, TRIG-02-004, TRIG-03-001, TRIG-03-002,
        TRIG-04-001, TRIG-12-001
    """
    return run_trigger(
        AddReportToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            report_id=body.report_id,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )


@router.post(
    "/{actor_id}/trigger/add-on-behalf-status",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Record a vendor's awareness or a deployer's deployment on their behalf.",
    description=(
        "A Case Manager or Case Owner records, on behalf of an existing "
        "participant (typically an invitee that has not yet replied), the "
        'vendor\'s awareness (``vf_state="Vf"``, v→V; PRM-06-003) or the '
        'deployer\'s deployment (``d_state="D"``, d→D; PRM-06-004). The '
        "target must already be a participant holding the asserted role: a "
        "non-participant target is refused and no participant is created "
        "(PRM-06-006, ADR-0084). Writes a "
        "ParticipantStatus for the target and queues an "
        "Add(ParticipantStatus, target=CaseParticipant) activity to the Case "
        'Manager. Fix readiness (``vf_state="VF"``, f→F) is refused: it is '
        "only ever self-declared by the Vendor (PRM-06-005). Returns the ids "
        "of the queued activity and the stored status."
    ),
    operation_id="actors_trigger_add_on_behalf_status",
    response_model=StatusResult,
)
def trigger_add_on_behalf_status(
    actor_id: str,
    body: AddOnBehalfStatusRequest,
    background_tasks: BackgroundTasks,
    dispatcher: TriggerDispatcher = Depends(get_trigger_dispatcher),
    actor_dl: DataLayer = Depends(get_trigger_dl),
) -> StatusResult:
    """Assert v→V or d→D on behalf of an existing vendor/deployer participant.

    Implements:
        TRIG-01-001, TRIG-01-002, TRIG-01-003, HTTP-03-005, TRIG-03-001,
        TRIG-03-002, TRIG-06-001, TRIG-06-002, TRIG-07-001, TRIG-12-001,
        PRM-06-003, PRM-06-004, PRM-06-005, PRM-06-006
    """
    # Field by field, not ``**body.model_dump()``: the parsed body is the
    # authority for what arrived (MV-11-005); the core request adds only the
    # path's ``actor_id`` (TRIG-06-001).
    return run_trigger(
        AddOnBehalfStatusTriggerRequest(
            actor_id=actor_id,
            case_id=body.case_id,
            target_actor_id=body.target_actor_id,
            vf_state=body.vf_state,
            d_state=body.d_state,
        ),
        dispatcher=dispatcher,
        dl=actor_dl,
        background_tasks=background_tasks,
    )
