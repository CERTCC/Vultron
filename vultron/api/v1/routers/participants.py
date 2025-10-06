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

import random

from fastapi import APIRouter

from vultron.as_vocab.activities.case_participant import (
    RemoveParticipantFromCase,
    AddStatusToParticipant,
    CreateParticipant,
    AddParticipantToCase,
)
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.case_participant import (
    CaseParticipant,
    FinderParticipant,
    VendorParticipant,
)
from vultron.as_vocab.objects.case_status import ParticipantStatus
from vultron.bt.roles.states import CVDRoles
from vultron.scripts import vocab_examples
from vultron.scripts.vocab_examples import (
    add_vendor_participant_to_case,
    add_finder_participant_to_case,
    add_coordinator_participant_to_case,
)

router = APIRouter(prefix="/participants", tags=["Participants"])
cp_router = APIRouter(
    prefix="/cases/{case_id}/participants", tags=["Participants"]
)


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
    "/examples",
    response_model=CaseParticipant,
    response_model_exclude_none=True,
    description="Get an example Case Participant object.",
    tags=["Examples"],
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
    tags=["Validation"],
)
def validate_participant(participant: CaseParticipant) -> CaseParticipant:
    """Validates a Case Participant object."""
    return participant


@cp_router.post(
    "/",
    response_model=CreateParticipant,
    response_model_exclude_none=True,
    description="Add a new participant to an existing Vulnerability Case. (This is a stub implementation.)",
    tags=["Cases", "Participants"],
)
async def add_actor_to_case_as_participant(
    case_id: str, actor: as_Actor, case_roles: list[CVDRoles]
) -> CreateParticipant:
    """Adds a participant to an existing VulnerabilityCase object."""
    return vocab_examples.create_participant()


@cp_router.post(
    "/{actor_id}",
    response_model=AddParticipantToCase,
    response_model_exclude_none=True,
    description="Associate an actor to an existing Vulnerability Case as a participant. (This is a stub implementation.)",
    tags=["Cases", "Participants", "Actors"],
)
async def add_existing_participant_to_case(
    case_id: str, participant_id: str
) -> AddParticipantToCase:
    """Adds a participant to an existing VulnerabilityCase object."""
    options = [
        add_vendor_participant_to_case,
        add_finder_participant_to_case,
        add_coordinator_participant_to_case,
    ]
    func = random.choice(options)
    return func()


@cp_router.get(
    "/{participant_id}/statuses",
    response_model=list[ParticipantStatus],
    response_model_exclude_none=True,
    description="Get the status history for a specific participant in a Vulnerability Case.",
    tags=["Statuses", "Participants"],
)
async def get_participant_statuses(
    case_id: str, participant_id: str
) -> list[ParticipantStatus]:
    statuses = []
    for _ in range(3):
        statuses.append(vocab_examples.participant_status())
    return statuses


@cp_router.post(
    path="/{participant_id}/statuses",
    response_model=AddStatusToParticipant,
    response_model_exclude_none=True,
    description="Add a new status to a participant in a Vulnerability Case. (This is a stub implementation.)",
    tags=["Statuses", "Participants"],
)
async def add_status_to_participant(
    case_id: str, participant_id: str, status: ParticipantStatus
) -> AddStatusToParticipant:
    """Adds a new status to a participant in a VulnerabilityCase."""
    return vocab_examples.add_status_to_participant()


@cp_router.delete(
    "/{participant_id}",
    response_model=RemoveParticipantFromCase,
    response_model_exclude_none=True,
    description="Remove a participant from a Vulnerability Case. (This is a stub implementation.)",
    tags=["Cases", "Participants"],
)
async def remove_participant_from_case(
    case_id: str, participant_id: str
) -> RemoveParticipantFromCase:
    """Removes a participant from a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.remove_participant_from_case()
