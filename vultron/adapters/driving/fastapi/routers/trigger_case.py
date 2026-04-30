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

Thin wrapper: validates request → calls adapter → returns response.
All domain logic lives in vultron.core.use_cases.triggers.case.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status

from vultron.adapters.driven.datalayer import get_datalayer
from vultron.adapters.driving.fastapi.deps import (
    get_canonical_actor_dl,
    get_trigger_service,
)
from vultron.adapters.driving.fastapi.errors import domain_error_translation
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.adapters.driving.fastapi.trigger_models import (
    AddNoteToCaseRequest,
    AddReportToCaseRequest,
    CaseTriggerRequest,
    CreateCaseRequest,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.ports.trigger_service import TriggerServicePort

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
    operation_id="actors_trigger_engage_case",
)
def trigger_engage_case(
    actor_id: str,
    body: CaseTriggerRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    actor_dl: DataLayer = Depends(get_canonical_actor_dl),
) -> dict:
    """
    Trigger the engage-case behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    with domain_error_translation():
        result = svc.engage_case(actor_id, body.case_id)
    background_tasks.add_task(
        outbox_handler, actor_id, actor_dl, get_datalayer()
    )
    return result


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
    operation_id="actors_trigger_defer_case",
)
def trigger_defer_case(
    actor_id: str,
    body: CaseTriggerRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    actor_dl: DataLayer = Depends(get_canonical_actor_dl),
) -> dict:
    """
    Trigger the defer-case behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    with domain_error_translation():
        result = svc.defer_case(actor_id, body.case_id)
    background_tasks.add_task(
        outbox_handler, actor_id, actor_dl, get_datalayer()
    )
    return result


@router.post(
    "/{actor_id}/trigger/add-note-to-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Add a note to a case.",
    description=(
        "Triggers the add-note-to-case behavior for the given actor. "
        "Creates a Note, adds it to the actor's local copy of the case, "
        "and queues Create(Note) and AddNoteToCase(Note, Case) activities "
        "in the actor's outbox for delivery to case participants."
    ),
    operation_id="actors_trigger_add_note_to_case",
)
def trigger_add_note_to_case(
    actor_id: str,
    body: AddNoteToCaseRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    actor_dl: DataLayer = Depends(get_canonical_actor_dl),
) -> dict:
    """
    Trigger the add-note-to-case behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-04-001, TB-06-001, TB-06-002
    """
    with domain_error_translation():
        result = svc.add_note_to_case(
            actor_id=actor_id,
            case_id=body.case_id,
            note_name=body.note_name,
            note_content=body.note_content,
            in_reply_to=body.in_reply_to,
        )
    background_tasks.add_task(
        outbox_handler, actor_id, actor_dl, get_datalayer()
    )
    return result


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
)
def trigger_create_case(
    actor_id: str,
    body: CreateCaseRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    actor_dl: DataLayer = Depends(get_canonical_actor_dl),
) -> dict:
    """
    Trigger the create-case behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-04-001
    """
    with domain_error_translation():
        result = svc.create_case(
            actor_id=actor_id,
            name=body.name,
            content=body.content,
            report_id=body.report_id,
        )
    background_tasks.add_task(
        outbox_handler, actor_id, actor_dl, get_datalayer()
    )
    return result


@router.post(
    "/{actor_id}/trigger/add-report-to-case",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Add a report to an existing case.",
    description=(
        "Links a VulnerabilityReport to an existing VulnerabilityCase and "
        "queues an AddReportToCaseActivity in the actor's outbox."
    ),
    operation_id="actors_trigger_add_report_to_case",
)
def trigger_add_report_to_case(
    actor_id: str,
    body: AddReportToCaseRequest,
    background_tasks: BackgroundTasks,
    svc: TriggerServicePort = Depends(get_trigger_service),
    actor_dl: DataLayer = Depends(get_canonical_actor_dl),
) -> dict:
    """
    Trigger the add-report-to-case behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-04-001
    """
    with domain_error_translation():
        result = svc.add_report_to_case(
            actor_id=actor_id,
            case_id=body.case_id,
            report_id=body.report_id,
        )
    background_tasks.add_task(
        outbox_handler, actor_id, actor_dl, get_datalayer()
    )
    return result
