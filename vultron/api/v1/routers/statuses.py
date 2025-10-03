#!/usr/bin/env python
"""
Vultron API Routers
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

from vultron.as_vocab.objects.case_status import CaseStatus, ParticipantStatus
from vultron.scripts import vocab_examples

router = APIRouter()

case_status_router = APIRouter(prefix="/case")
participant_status_router = APIRouter(prefix="/participant")

router.include_router(case_status_router)
router.include_router(participant_status_router)


@case_status_router.get(
    "/validate",
    response_model=CaseStatus,
    response_model_exclude_none=True,
    description="Validates a CaseStatus object.",
)
def validate_case_status(case_status: CaseStatus) -> CaseStatus:
    """Validates a CaseStatus object."""
    return case_status


@case_status_router.get(
    "/example",
    response_model=CaseStatus,
    response_model_exclude_none=True,
    description="Returns an example CaseStatus object.",
)
def example_case_status() -> CaseStatus:
    """Returns an example CaseStatus object."""
    return vocab_examples.case_status()


@participant_status_router.get(
    "/validate",
    response_model=ParticipantStatus,
    response_model_exclude_none=True,
    description="Validates a ParticipantStatus object.",
)
def validate_participant_status(
    status: ParticipantStatus,
) -> ParticipantStatus:
    """Validates a ParticipantStatus object."""
    return status


@participant_status_router.get(
    "/example",
    response_model=ParticipantStatus,
    response_model_exclude_none=True,
    description="Returns an example ParticipantStatus object.",
)
def example_participant_status() -> ParticipantStatus:
    """Returns an example ParticipantStatus object."""
    return vocab_examples.participant_status()
