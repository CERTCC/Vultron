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

from vultron.as_vocab.activities.actor import (
    RecommendActor,
    AcceptActorRecommendation,
    RejectActorRecommendation,
)
from vultron.as_vocab.activities.case import (
    CreateCase,
    AddReportToCase,
    RmEngageCase,
    RmCloseCase,
    RmDeferCase,
    AddNoteToCase,
    UpdateCase,
    RmAcceptInviteToCase,
    RmRejectInviteToCase,
    CreateCaseStatus,
)
from vultron.as_vocab.activities.case_participant import (
    AddParticipantToCase,
    CreateParticipant,
)
from vultron.as_vocab.base.objects.activities.transitive import as_Undo
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.case_status import CaseStatus, ParticipantStatus
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.bt.roles.states import CVDRoles
from vultron.scripts import vocab_examples
from vultron.scripts.vocab_examples import (
    add_vendor_participant_to_case,
    add_finder_participant_to_case,
    add_coordinator_participant_to_case,
)

router = APIRouter()
case_router = APIRouter(prefix="/{case_id}")

reports_router = APIRouter(prefix="/reports")
report_router = APIRouter(prefix="/{report_id}")
reports_router.include_router(report_router)

participants_router = APIRouter(prefix="/participants")
participant_router = APIRouter(prefix="/{participant_id}")
participants_router.include_router(participant_router)

notes_router = APIRouter(prefix="/notes")
note_router = APIRouter(prefix="/{note_id}")
notes_router.include_router(note_router)


offers_router = APIRouter(prefix="/offers")
offer_router = APIRouter(prefix="/{offer_id}")
offers_router.include_router(offer_router)

invitations_router = APIRouter(prefix="/invitations")
invitation_router = APIRouter(prefix="/{invitation_id}")
invitations_router.include_router(invitation_router)


router.include_router(case_router)
case_router.include_router(reports_router)
case_router.include_router(participants_router)
case_router.include_router(notes_router)
case_router.include_router(offers_router)
case_router.include_router(invitations_router)


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
    "/",
    response_model=CreateCase,
    response_model_exclude_none=True,
    description="Create a new Vulnerability Case object. (This is a stub implementation.)",
)
async def create_case(case: VulnerabilityCase) -> CreateCase:
    """Creates a VulnerabilityCase object."""
    return vocab_examples.create_case()


@case_router.post(
    "/reports",
    response_model=AddReportToCase,
    response_model_exclude_none=True,
    description="Add a new report to an existing Vulnerability Case. (This is a stub implementation.)",
)
async def post_report_to_case(
    case_id: str, report: VulnerabilityReport
) -> AddReportToCase:
    """Adds a new report to an existing VulnerabilityCase object."""
    return vocab_examples.add_report_to_case()


@report_router.put(
    "/",
    response_model=AddReportToCase,
    response_model_exclude_none=True,
    description="Associate an existing report to an existing Vulnerability Case. (This is a stub implementation.)",
)
async def add_report_to_case(case_id: str, report_id: str) -> AddReportToCase:
    """Adds a report to an existing VulnerabilityCase object."""
    return vocab_examples.add_report_to_case()


@participants_router.post(
    "/",
    response_model=CreateParticipant,
    response_model_exclude_none=True,
    description="Add a new participant to an existing Vulnerability Case. (This is a stub implementation.)",
)
async def add_actor_to_case_as_participant(
    case_id: str, actor: as_Actor, case_roles: list[CVDRoles]
) -> CreateParticipant:
    """Adds a participant to an existing VulnerabilityCase object."""
    return vocab_examples.create_participant()


@participant_router.put(
    "/",
    response_model=AddParticipantToCase,
    response_model_exclude_none=True,
    description="Associate an existing participant to an existing Vulnerability Case. (This is a stub implementation.)",
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


@case_router.put(
    "/engage",
    response_model=RmEngageCase,
    response_model_exclude_none=True,
    description="Engage a Vulnerability Case by ID. (This is a stub implementation.)",
)
async def engage_case_by_id(case_id: str) -> RmEngageCase:
    """Engage a VulnerabilityCase by ID. (This is a stub implementation.)"""
    # In a real implementation, you would retrieve and engage the case from a database.
    return vocab_examples.engage_case()


@case_router.put(
    "/close",
    response_model=RmCloseCase,
    response_model_exclude_none=True,
    description="Close a Vulnerability Case by ID. (This is a stub implementation.)",
)
async def close_case_by_id(case_id: str) -> RmCloseCase:
    """Close a VulnerabilityCase by ID. (This is a stub implementation.)"""
    # In a real implementation, you would retrieve and close the case from a database.
    return vocab_examples.close_case()


@case_router.put(
    "/defer",
    response_model=RmDeferCase,
    response_model_exclude_none=True,
    description="Defer a Vulnerability Case by ID. (This is a stub implementation.)",
)
async def defer_case_by_id(case_id: str) -> RmDeferCase:
    """Defer a VulnerabilityCase by ID. (This is a stub implementation.)"""
    # In a real implementation, you would retrieve and defer the case from a database.
    return vocab_examples.defer_case()


@case_router.put(
    "/reengage",
    response_model=as_Undo,
    response_model_exclude_none=True,
    description="Re-engage a Vulnerability Case by ID. (This is a stub implementation.)",
)
async def reengage_case_by_id(case_id: str) -> as_Undo:
    """Re-engage a VulnerabilityCase by ID. (This is a stub implementation.)"""
    # In a real implementation, you would retrieve and re-engage the case from a database.
    return vocab_examples.reengage_case()


@notes_router.post(
    "/",
    response_model=AddNoteToCase,
    response_model_exclude_none=True,
    description="Add a note to a case. (This is a stub implementation.)",
)
async def add_note_to_case(case_id: str):
    """Stub for adding a note to a case."""
    return vocab_examples.add_note_to_case()


@note_router.put(
    "/",
    response_model=AddNoteToCase,
    response_model_exclude_none=True,
    description="Associate an existing note to a case. (This is a stub implementation.)",
)
async def add_existing_note_to_case(
    case_id: str, note_id: str
) -> AddNoteToCase:
    """Stub for associating an existing note to a case."""
    return vocab_examples.add_note_to_case()


@case_router.put(
    "/",
    response_model=UpdateCase,
    response_model_exclude_none=True,
    description="Update a Vulnerability Case. (This is a stub implementation.)",
)
async def update_case(case_id: str, case: VulnerabilityCase) -> UpdateCase:
    """Update a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.update_case()


@offers_router.put(
    "/actors/{actor_id}",
    response_model=RecommendActor,
    response_model_exclude_none=True,
    description="Recommend an Actor for a Vulnerability Case. (This is a stub implementation.)",
)
async def recommend_actor_for_case(
    case_id: str, actor_id: str
) -> RecommendActor:
    """Recommend an Actor for a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.recommend_actor()


@offer_router.put(
    "/accept",
    response_model=AcceptActorRecommendation,
    response_model_exclude_none=True,
    description="Accept an Actor recommendation for a Vulnerability Case. (This is a stub implementation.)",
)
async def accept_actor_recommendation_for_case(
    case_id: str, offer_id: str
) -> AcceptActorRecommendation:
    """Accept an Actor recommendation for a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.accept_actor_recommendation()


@offer_router.put(
    "/reject",
    response_model=RejectActorRecommendation,
    response_model_exclude_none=True,
    description="Reject an Actor recommendation for a Vulnerability Case. (This is a stub implementation.)",
)
async def reject_actor_recommendation_for_case(
    case_id: str, offer_id: str
) -> RejectActorRecommendation:
    """Reject an Actor recommendation for a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.reject_actor_recommendation()


@invitations_router.post(
    "/actors/{actor_id}",
    response_model="InviteActorToCase",
    response_model_exclude_none=True,
    description="Invite an Actor to a Vulnerability Case. (This is a stub implementation.)",
    summary="Invite Actor to Case",
)
async def invite_actor_to_case(
    case_id: str, actor_id: str
) -> "InviteActorToCase":
    """Invite an Actor to a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.invite_to_case()


@invitation_router.put(
    "/accept",
    response_model=RmAcceptInviteToCase,
    response_model_exclude_none=True,
    description="Accept an invitation to a Vulnerability Case. (This is a stub implementation.)",
    summary="Accept Invitation to Case",
)
async def accept_invitation_to_case(
    case_id: str, invitation_id: str
) -> RmAcceptInviteToCase:
    """Accept an invitation to a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.accept_invite_to_case()


@invitation_router.put(
    "/reject",
    response_model=RmRejectInviteToCase,
    response_model_exclude_none=True,
    description="Reject an invitation to a Vulnerability Case. (This is a stub implementation.)",
    summary="Reject Invitation to Case",
)
async def reject_invitation_to_case(
    case_id: str, invitation_id: str
) -> RmRejectInviteToCase:
    """Reject an invitation to a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.reject_invite_to_case()


statuses_router = APIRouter(prefix="/statuses")
case_router.include_router(statuses_router)


@statuses_router.get(
    "/",
    response_model=list[CaseStatus],
    response_model_exclude_none=True,
    description="Get the status history for a Vulnerability Case.",
)
async def get_case_statuses(case_id: str) -> list[CaseStatus]:
    statuses = []
    for _ in range(3):
        statuses.append(vocab_examples.case_status())
    return statuses


@statuses_router.get(
    "/example",
    response_model=CaseStatus,
    response_model_exclude_none=True,
    description="Get an example Case Status object.",
)
async def get_example_case_status() -> CaseStatus:
    """Returns an example CaseStatus object."""
    return vocab_examples.case_status()


@statuses_router.post(
    "/",
    response_model=CreateCaseStatus,
    response_model_exclude_none=True,
    description="Create a new Case Status for a Vulnerability Case. (This is a stub implementation.)",
)
async def create_case_status(
    case_id: str, status: CaseStatus
) -> CreateCaseStatus:
    """Creates a new CaseStatus for a VulnerabilityCase."""
    return vocab_examples.create_case_status()


@participant_router.get(
    "/statuses",
    response_model=list[ParticipantStatus],
    response_model_exclude_none=True,
    description="Get the status history for a participant in a Vulnerability Case.",
)
async def get_participant_statuses(
    case_id: str, participant_id: str
) -> list[ParticipantStatus]:
    statuses = []
    for _ in range(3):
        statuses.append(vocab_examples.participant_status())
    return statuses
