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

Thin wrapper: validates request → calls service → returns response.
All domain logic lives in vultron.api.v2.backend.trigger_services.report.
"""

from fastapi import APIRouter, Depends, status

from vultron.api.v2.backend.trigger_services._models import (
    CloseReportRequest,
    InvalidateReportRequest,
    RejectReportRequest,
    ValidateReportRequest,
)
from vultron.api.v2.backend.trigger_services.report import (
    svc_close_report,
    svc_invalidate_report,
    svc_reject_report,
    svc_validate_report,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.adapters.driven.datalayer_tinydb import get_datalayer

router = APIRouter(prefix="/actors", tags=["Triggers"])


@router.post(
    "/{actor_id}/trigger/validate-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger report validation.",
    description=(
        "Triggers the validate-report behavior for the given actor. "
        "Invokes the ValidateReportBT tree via the bridge layer and "
        "returns the resulting ActivityStreams activity (TB-04-001)."
    ),
)
def trigger_validate_report(
    actor_id: str,
    body: ValidateReportRequest,
    dl: DataLayer = Depends(get_datalayer),
) -> dict:
    """
    Trigger the validate-report behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-03-001, TB-03-002, TB-03-003,
        TB-04-001, TB-05-001, TB-05-002, TB-06-001, TB-06-002, TB-07-001
    """
    return svc_validate_report(actor_id, body.offer_id, body.note, dl)


@router.post(
    "/{actor_id}/trigger/invalidate-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger report invalidation.",
    description=(
        "Triggers the invalidate-report behavior for the given actor. "
        "Emits a TentativeReject(Offer(VulnerabilityReport)) activity "
        "(RmInvalidateReport) and returns it in the response body (TB-04-001). "
        "Updates the offer status to TENTATIVELY_REJECTED and the report "
        "status to INVALID."
    ),
)
def trigger_invalidate_report(
    actor_id: str,
    body: InvalidateReportRequest,
    dl: DataLayer = Depends(get_datalayer),
) -> dict:
    """
    Trigger the invalidate-report behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-03-003, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return svc_invalidate_report(actor_id, body.offer_id, body.note, dl)


@router.post(
    "/{actor_id}/trigger/reject-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger hard-close of a report.",
    description=(
        "Triggers the reject-report behavior for the given actor. "
        "Emits a Reject(Offer(VulnerabilityReport)) activity (RmCloseReport) "
        "and returns it in the response body (TB-04-001). "
        "A non-empty note is required (TB-03-004). "
        "Updates the offer status to REJECTED and the report status to CLOSED."
    ),
)
def trigger_reject_report(
    actor_id: str,
    body: RejectReportRequest,
    dl: DataLayer = Depends(get_datalayer),
) -> dict:
    """
    Trigger the reject-report (hard-close) behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-03-004, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return svc_reject_report(actor_id, body.offer_id, body.note, dl)


@router.post(
    "/{actor_id}/trigger/close-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger RM lifecycle closure of a report.",
    description=(
        "Triggers the close-report behavior for the given actor. "
        "Emits a Reject(Offer(VulnerabilityReport)) activity (RmCloseReport) "
        "representing the RM → C (CLOSED) transition, and returns it in the "
        "response body (TB-04-001). "
        "Updates the offer status to REJECTED and the report status to CLOSED. "
        "Unlike reject-report (which hard-rejects before validation), this "
        "endpoint closes a report that has already progressed through the RM "
        "lifecycle. Returns HTTP 409 if the report is already CLOSED."
    ),
)
def trigger_close_report(
    actor_id: str,
    body: CloseReportRequest,
    dl: DataLayer = Depends(get_datalayer),
) -> dict:
    """
    Trigger the close-report (RM → CLOSED) behavior for the given actor.

    Implements:
        TB-01-001, TB-01-002, TB-01-003, TB-02-001, TB-03-001, TB-03-002,
        TB-03-003, TB-04-001, TB-06-001, TB-06-002, TB-07-001
    """
    return svc_close_report(actor_id, body.offer_id, body.note, dl)
