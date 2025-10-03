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

from vultron.as_vocab.activities.case import AddReportToCase
from vultron.as_vocab.activities.report import (
    RmCloseReport,
    RmInvalidateReport,
    RmValidateReport,
    RmReadReport,
    RmSubmitReport,
    RmCreateReport,
)
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.scripts import vocab_examples

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "/example",
    response_model=VulnerabilityReport,
    response_model_exclude_none=True,
    description="Get an example Vulnerability Report object.",
    tags=["examples"],
)
async def get_report() -> VulnerabilityReport:
    """Returns an example report object."""
    report = VulnerabilityReport(content="This is an example report.")
    return report


@router.post(
    "/validate",
    response_model=VulnerabilityReport,
    response_model_exclude_none=True,
    summary="Validate Report object format",
    description="Validates a Vulnerability Report object.",
)
async def validate_report(report: VulnerabilityReport) -> VulnerabilityReport:
    """Validates a VulnerabilityReport object."""
    return report


@router.post(
    "/create",
    response_model=RmCreateReport,
    response_model_exclude_none=True,
    description="Create a new Vulnerability Report object. (This is a stub implementation.)",
)
async def create_case(case: VulnerabilityCase) -> RmCreateReport:
    """Creates a VulnerabilityCase object."""
    return vocab_examples.create_report()


@router.post(
    "/submit",
    response_model=RmSubmitReport,
    response_model_exclude_none=True,
    description="Submit a Vulnerability Report. (This is a stub implementation.)",
)
async def submit_case(case: VulnerabilityCase) -> RmSubmitReport:
    """Submit a new VulnerabilityCase object."""
    # In a real implementation, you would save the case to a database or perform other actions.
    return vocab_examples.submit_report()


@router.put(
    "/{id}/read",
    response_model=RmReadReport,
    response_model_exclude_none=True,
    description="Acknowledge a report has been read. (This is a stub implementation.)",
)
async def read_case(id: str) -> RmReadReport:
    """Read a VulnerabilityCase by ID. (This is a stub implementation.)"""
    # In a real implementation, you would retrieve the case from a database.
    return vocab_examples.read_report()


@router.put(
    "/{id}/validate",
    response_model=RmValidateReport,
    response_model_exclude_none=True,
    description="Validate a Vulnerability Case by ID. (This is a stub implementation.)",
)
async def validate_case_by_id(id: str) -> RmValidateReport:
    """Validate a VulnerabilityCase by ID. (This is a stub implementation.)"""
    # In a real implementation, you would retrieve and validate the case from a database.
    return vocab_examples.validate_report()


@router.put(
    "/{id}/invalidate",
    response_model=RmInvalidateReport,
    response_model_exclude_none=True,
    description="Invalidate a Vulnerability Case by ID. (This is a stub implementation.)",
)
async def invalidate_case_by_id(id: str) -> RmInvalidateReport:
    """Invalidate a VulnerabilityCase by ID. (This is a stub implementation.)"""
    # In a real implementation, you would retrieve and invalidate the case from a database.
    return vocab_examples.invalidate_report()


@router.put(
    "/{id}/close",
    response_model=RmCloseReport,
    response_model_exclude_none=True,
    description="Close a Vulnerability Case by ID. (This is a stub implementation.)",
)
async def close_case_by_id(id: str) -> RmCloseReport:
    """Close a VulnerabilityCase by ID. (This is a stub implementation.)"""
    # In a real implementation, you would retrieve and close the case from a database.
    return vocab_examples.close_report()


@router.put(
    "/{id}/cases/{case_id}",
    response_model=AddReportToCase,
    response_model_exclude_none=True,
    description="Add a report to an existing Vulnerability Case. (This is a stub implementation.)",
)
async def add_report_to_case(id: str, case_id: str) -> AddReportToCase:
    """Adds a report to an existing VulnerabilityCase object."""
    return vocab_examples.add_report_to_case()
