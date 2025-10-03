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

from vultron.as_vocab.objects.case_participant import (
    CaseParticipant,
    FinderParticipant,
    VendorParticipant,
)
from vultron.scripts import vocab_examples

router = APIRouter()


def _participant_examples() -> list[CaseParticipant]:
    finder = vocab_examples.finder()
    vendor = vocab_examples.vendor()
    coordinator = vocab_examples.coordinator()

    participants = []
    _finder = FinderParticipant(
        id=f"example/participants/{finder.as_id}",
        name=finder.name,
        actor=finder.as_id,
        context="example",
    )
    participants.append(_finder)
    _vendor = VendorParticipant(
        id=f"example/participants/{vendor.as_id}",
        name=vendor.name,
        actor=vendor.as_id,
        context="example",
    )
    participants.append(_vendor)
    _coordinator = CaseParticipant(
        id=f"example/participants/{coordinator.as_id}",
        name=coordinator.name,
        actor=coordinator.as_id,
        context="example",
    )
    participants.append(_coordinator)
    return participants


@router.get(
    "/",
    response_model=list[CaseParticipant],
    response_model_exclude_none=True,
    description="Get all participant objects (stub implementation).",
)
async def get_participants(case_id: str) -> list[CaseParticipant]:
    """
    Get all participants
    """
    return _participant_examples()


@router.get(
    "/example",
    response_model=CaseParticipant,
    response_model_exclude_none=True,
    description="Get an example Case Participant object.",
)
def get_example_participant() -> CaseParticipant:
    """
    Get an example Case Participant object
    """
    options = _participant_examples()
    import random

    return random.choice(options)


@router.post(
    "/validate",
    response_model=CaseParticipant,
    response_model_exclude_none=True,
    summary="Validate Case Participant object format",
    description="Validates a Case Participant object.",
)
def validate_participant(participant: CaseParticipant) -> CaseParticipant:
    """Validates a Case Participant object."""
    return participant
