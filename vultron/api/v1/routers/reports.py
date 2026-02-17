#!/usr/bin/env python
"""
Vultron API Report Routers
"""

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
from fastapi import APIRouter

from vultron.as_vocab.activities.report import (
    RmCloseReport,
    RmInvalidateReport,
    RmValidateReport,
    RmReadReport,
    RmSubmitReport,
    RmCreateReport,
)
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.scripts import vocab_examples

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "/",
    response_model=list[VulnerabilityReport],
    response_model_exclude_none=True,
    description="Get all Vulnerability Report objects. (scoped to the actor) (This is a stub implementation.)",
)
def get_reports() -> list[VulnerabilityReport]:
    """Returns a list of all report objects."""
    return [vocab_examples.gen_report()]


@router.post(
    "/",
    description="Create a new Vulnerability Report object. (This is a stub implementation.)",
)
def create_report(report: VulnerabilityReport) -> RmCreateReport:
    """Creates a VulnerabilityReport object."""
    return vocab_examples.create_report()


# Question: Is this redundant to create_report?
# Answer: No, because this represents an Offer(Report) activity vs a Create(Report) activity
@router.post(
    "/submit",
    response_model=RmSubmitReport,
    response_model_exclude_none=True,
    description="Submit a Vulnerability Report. (This is a stub implementation.)",
)
async def submit_report(report: VulnerabilityReport) -> RmSubmitReport:
    """Submit a new VulnerabilityCase object."""
    # In a real implementation, you would save the case to a database or perform other actions.
    return vocab_examples.submit_report()


@router.put(
    "/{report_id}/read",
    response_model=RmReadReport,
    response_model_exclude_none=True,
    description="Acknowledge a report has been read. (This is a stub implementation.)",
)
async def read_case(id: str) -> RmReadReport:
    """Read a VulnerabilityCase by ID. (This is a stub implementation.)"""
    # In a real implementation, you would retrieve the case from a database.
    return vocab_examples.read_report()


@router.put(
    "/{report_id}/valid",
    response_model=RmValidateReport,
    response_model_exclude_none=True,
    description="Validate a Vulnerability Case by ID. (This is a stub implementation.)",
)
async def validate_case_by_id(id: str) -> RmValidateReport:
    """Validate a VulnerabilityCase by ID. (This is a stub implementation.)"""
    # In a real implementation, you would retrieve and validate the case from a database.
    return vocab_examples.validate_report(verbose=True)


@router.put(
    "/{report_id}/invalid",
    response_model=RmInvalidateReport,
    response_model_exclude_none=True,
    description="Invalidate a Vulnerability Case by ID. (This is a stub implementation.)",
)
async def invalidate_case_by_id(id: str) -> RmInvalidateReport:
    """Invalidate a VulnerabilityCase by ID. (This is a stub implementation.)"""
    # In a real implementation, you would retrieve and invalidate the case from a database.
    return vocab_examples.invalidate_report(verbose=True)


@router.put(
    "/{report_id}/close",
    response_model=RmCloseReport,
    response_model_exclude_none=True,
    description="Close a Vulnerability Case by ID. (This is a stub implementation.)",
)
async def close_case_by_id(id: str) -> RmCloseReport:
    """Close a VulnerabilityCase by ID. (This is a stub implementation.)"""
    # In a real implementation, you would retrieve and close the case from a database.
    return vocab_examples.close_report(verbose=True)
