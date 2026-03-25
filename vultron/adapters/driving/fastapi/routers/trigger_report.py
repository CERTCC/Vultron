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

Thin wrapper: validates request → calls adapter → returns response.
All domain logic lives in vultron.core.use_cases.triggers.report.
"""

from fastapi import APIRouter, Depends, Path, status

from vultron.adapters.driving.fastapi._trigger_adapter import (
    close_report_trigger,
    invalidate_report_trigger,
    reject_report_trigger,
    validate_report_trigger,
)
from vultron.adapters.driving.fastapi.trigger_models import (
    CloseReportRequest,
    InvalidateReportRequest,
    RejectReportRequest,
    ValidateReportRequest,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.adapters.driven.datalayer_tinydb import get_datalayer

router = APIRouter(prefix="/actors", tags=["Triggers"])


def _actor_dl(actor_id: str = Path(...)) -> DataLayer:  # noqa: ARG001
    """FastAPI dependency: return the shared DataLayer for trigger use cases.

    Operational data (actors, offers, reports, cases) is stored in the shared
    DataLayer.  The ``actor_id`` path parameter is accepted but unused so that
    ``app.dependency_overrides[_actor_dl]`` works in tests (ADR-0012).
    """
    return get_datalayer()


@router.post(
    "/{actor_id}/trigger/validate-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger report validation.",
    description=(
        "Triggers the validate-report behavior for the given actor. "
        "Invokes the ValidateReportBT tree via the bridge layer and "
        "returns the resulting ActivityStreams activity (TB-04-001)."
    ),
    operation_id="actors_trigger_validate_report",
)
def trigger_validate_report(
    actor_id: str,
    body: ValidateReportRequest,
    dl: DataLayer = Depends(_actor_dl),
) -> dict:
    """
    Trigger the validate-report behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-03-001, TB-03-002, TB-03-003,
        TB-04-001, TB-05-001, TB-05-002, TB-06-001, TB-06-002, TB-07-001
    """
    return validate_report_trigger(actor_id, body.offer_id, body.note, dl)


@router.post(
    "/{actor_id}/trigger/invalidate-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger report invalidation.",
    description=(
        "Triggers the invalidate-report behavior for the given actor. "
        "Emits a TentativeReject(Offer(VulnerabilityReport)) activity "
        "(RmInvalidateReportActivity) and returns it in the response body (TB-04-001). "
        "Persists a ParticipantStatus record with RM.INVALID for the actor "
        "and report."
    ),
    operation_id="actors_trigger_invalidate_report",
)
def trigger_invalidate_report(
    actor_id: str,
    body: InvalidateReportRequest,
    dl: DataLayer = Depends(_actor_dl),
) -> dict:
    """
    Trigger the invalidate-report behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-03-003, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return invalidate_report_trigger(actor_id, body.offer_id, body.note, dl)


@router.post(
    "/{actor_id}/trigger/reject-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger hard-close of a report.",
    description=(
        "Triggers the reject-report behavior for the given actor. "
        "Emits a Reject(Offer(VulnerabilityReport)) activity (RmCloseReportActivity) "
        "and returns it in the response body (TB-04-001). "
        "A non-empty note is required (TB-03-004). "
        "Persists a ParticipantStatus record with RM.CLOSED for the actor "
        "and report."
    ),
    operation_id="actors_trigger_reject_report",
)
def trigger_reject_report(
    actor_id: str,
    body: RejectReportRequest,
    dl: DataLayer = Depends(_actor_dl),
) -> dict:
    """
    Trigger the reject-report (hard-close) behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-03-004, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return reject_report_trigger(actor_id, body.offer_id, body.note, dl)


@router.post(
    "/{actor_id}/trigger/close-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger RM lifecycle closure of a report.",
    description=(
        "Triggers the close-report behavior for the given actor. "
        "Emits a Reject(Offer(VulnerabilityReport)) activity (RmCloseReportActivity) "
        "representing the RM → C (CLOSED) transition, and returns it in the "
        "response body (TB-04-001). "
        "Persists a ParticipantStatus record with RM.CLOSED for the actor "
        "and report. "
        "Unlike reject-report (which hard-rejects before validation), this "
        "endpoint closes a report that has already progressed through the RM "
        "lifecycle. Returns HTTP 409 if the report is already CLOSED."
    ),
    operation_id="actors_trigger_close_report",
)
def trigger_close_report(
    actor_id: str,
    body: CloseReportRequest,
    dl: DataLayer = Depends(_actor_dl),
) -> dict:
    """
    Trigger the close-report (RM → CLOSED) behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-03-003, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return close_report_trigger(actor_id, body.offer_id, body.note, dl)
