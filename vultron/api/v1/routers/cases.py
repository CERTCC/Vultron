#!/usr/bin/env python
"""
Vultron API Case Routers
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

import random

from fastapi import APIRouter

from vultron.as_vocab.activities.case import CreateCase, AddReportToCase
from vultron.as_vocab.activities.case_participant import AddParticipantToCase
from vultron.as_vocab.objects.case_participant import CaseParticipant
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.scripts import vocab_examples
from vultron.scripts.vocab_examples import (
    add_vendor_participant_to_case,
    add_finder_participant_to_case,
    add_coordinator_participant_to_case,
)

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

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get(
    "/",
    response_model=list[VulnerabilityCase],
    response_model_exclude_none=True,
    description="Get a list of example Vulnerability Case objects.",
)
async def get_cases() -> list[VulnerabilityCase]:
    """Returns a list of example VulnerabilityCase objects."""
    case_list = [vocab_examples.case(random_id=True) for _ in range(5)]
    return case_list


@router.get(
    "/example",
    response_model=VulnerabilityCase,
    response_model_exclude_none=True,
    description="Get an example Vulnerability Case object.",
    tags=["examples"],
)
async def get_case() -> VulnerabilityCase:
    """Returns an example VulnerabilityCase object."""
    return vocab_examples.case()


@router.post(
    "/validate",
    response_model=VulnerabilityCase,
    response_model_exclude_none=True,
    description="Validates a Vulnerability Case object.",
    summary="Validate Case object format",
)
async def validate_case(case: VulnerabilityCase) -> VulnerabilityCase:
    """Validates a VulnerabilityCase object."""
    return case


@router.post(
    "/create",
    response_model=CreateCase,
    response_model_exclude_none=True,
    description="Create a new Vulnerability Case object. (This is a stub implementation.)",
    tags=["create"],
)
async def create_case(case: VulnerabilityCase) -> CreateCase:
    """Creates a VulnerabilityCase object."""
    return vocab_examples.create_case()


@router.post(
    "/{id}/add_report",
    response_model=AddReportToCase,
    response_model_exclude_none=True,
    description="Add a new report to an existing Vulnerability Case. (This is a stub implementation.)",
)
async def add_new_report_to_case(
    id: str, report: VulnerabilityReport
) -> AddReportToCase:
    """Adds a new report to an existing VulnerabilityCase object."""
    return vocab_examples.add_report_to_case()


@router.put(
    "/{id}/add_report/{report_id}",
    response_model=AddReportToCase,
    response_model_exclude_none=True,
    description="Associate an existing report to an existing Vulnerability Case. (This is a stub implementation.)",
)
async def add_report_to_case(id: str, report_id: str) -> AddReportToCase:
    """Adds a report to an existing VulnerabilityCase object."""
    return vocab_examples.add_report_to_case()


@router.post(
    "/{id}/add_participant",
    response_model=AddParticipantToCase,
    response_model_exclude_none=True,
    description="Add a new participant to an existing Vulnerability Case. (This is a stub implementation.)",
)
async def add_participant_to_case(
    id: str, participant: CaseParticipant
) -> AddParticipantToCase:
    """Adds a participant to an existing VulnerabilityCase object."""
    options = [
        add_vendor_participant_to_case,
        add_finder_participant_to_case,
        add_coordinator_participant_to_case,
    ]
    func = random.choice(options)
    return func()


@router.put(
    "/{id}/add_participant/{participant_id}",
    response_model=AddParticipantToCase,
    response_model_exclude_none=True,
    description="Associate an existing participant to an existing Vulnerability Case. (This is a stub implementation.)",
)
async def add_existing_participant_to_case(
    id: str, participant_id: str
) -> AddParticipantToCase:
    """Adds a participant to an existing VulnerabilityCase object."""
    options = [
        add_vendor_participant_to_case,
        add_finder_participant_to_case,
        add_coordinator_participant_to_case,
    ]
    func = random.choice(options)
    return func()
