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
    AcceptCaseOwnershipTransfer,
    RejectCaseOwnershipTransfer,
    AddStatusToCase,
)
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Undo,
    as_Create,
)
from vultron.as_vocab.objects.case_participant import CaseParticipant
from vultron.as_vocab.objects.case_status import CaseStatus, ParticipantStatus
from vultron.as_vocab.objects.embargo_event import EmbargoEvent
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.scripts import vocab_examples

router = APIRouter(prefix="/cases", tags=["Cases"])
case_router = APIRouter(prefix="/cases/{case_id}", tags=["Cases"])


# Generic case methods
@router.get(
    "/examples",
    response_model=VulnerabilityCase,
    response_model_exclude_none=True,
    description="Get an example Vulnerability Case object.",
    tags=["Examples"],
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
    tags=["Cases"],
)
async def validate_case(case: VulnerabilityCase) -> VulnerabilityCase:
    """Validates a VulnerabilityCase object."""
    return case


@router.get(
    "/",
    response_model=list[VulnerabilityCase],
    response_model_exclude_none=True,
    description="Get a list of Vulnerability Case objects.",
)
async def get_cases() -> list[VulnerabilityCase]:
    """Returns a list of example VulnerabilityCase objects."""
    case_list = [vocab_examples.case(random_id=True) for _ in range(3)]
    return case_list


@router.post(
    "/",
    response_model=CreateCase,
    response_model_exclude_none=True,
    description="Create a new Vulnerability Case object. (This is a stub implementation.)",
    tags=["Cases"],
)
async def create_case(case: VulnerabilityCase) -> CreateCase:
    """Creates a VulnerabilityCase object."""
    return vocab_examples.create_case()


# Case-specific methods


@case_router.put(
    "/",
    response_model=UpdateCase,
    response_model_exclude_none=True,
    description="Update a Vulnerability Case. (This is a stub implementation.)",
    tags=["Cases"],
)
async def update_case(case_id: str, case: VulnerabilityCase) -> UpdateCase:
    """Update a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.update_case()


@case_router.post(
    "/reports",
    response_model=AddReportToCase,
    response_model_exclude_none=True,
    description="Add a new report to an existing Vulnerability Case. (This is a stub implementation.)",
    tags=["Cases", "Reports"],
)
async def post_report_to_case(
    case_id: str, report: VulnerabilityReport
) -> AddReportToCase:
    """Adds a new report to an existing VulnerabilityCase object."""
    return vocab_examples.add_report_to_case()


@case_router.put(
    "/engage",
    response_model=RmEngageCase,
    response_model_exclude_none=True,
    description="Engage a Vulnerability Case by ID. (This is a stub implementation.)",
    tags=["Cases"],
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
    tags=["Cases"],
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
    tags=["Cases"],
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
    tags=["Cases"],
)
async def reengage_case_by_id(case_id: str) -> as_Undo:
    """Re-engage a VulnerabilityCase by ID. (This is a stub implementation.)"""
    # In a real implementation, you would retrieve and re-engage the case from a database.
    return vocab_examples.reengage_case()


@case_router.put(
    "/reports/{report_id}",
    response_model=AddReportToCase,
    response_model_exclude_none=True,
    description="Associate an existing report to an existing Vulnerability Case. (This is a stub implementation.)",
    tags=["Cases", "Reports"],
)
async def add_report_to_case(case_id: str, report_id: str) -> AddReportToCase:
    """Adds a report to an existing VulnerabilityCase object."""
    return vocab_examples.add_report_to_case()


@router.post(
    "/{case_id}/notes",
    response_model=as_Create,
    response_model_exclude_none=True,
    description="Add a note to a case. (This is a stub implementation.)",
    tags=["Cases", "Notes"],
)
async def add_note_to_case(case_id: str):
    """Stub for adding a note to a case."""
    return vocab_examples.create_note()


@router.put(
    "/{case_id}/notes/{note_id}",
    response_model=AddNoteToCase,
    response_model_exclude_none=True,
    description="Associate an existing note to a case. (This is a stub implementation.)",
    tags=["Cases", "Notes"],
)
async def add_existing_note_to_case(
    case_id: str, note_id: str
) -> AddNoteToCase:
    """Stub for associating an existing note to a case."""
    return vocab_examples.add_note_to_case()


# Recommend Actor methods


@router.post(
    "/{case_id}/recommendations",
    response_model=RecommendActor,
    response_model_exclude_none=True,
    description="Recommend an Actor for a Vulnerability Case. (This is a stub implementation.)",
    tags=["Cases", "Actors", "Recommend Actors"],
)
async def recommend_actor_for_case(
    case_id: str, actor_id: str
) -> RecommendActor:
    """Recommend an Actor for a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.recommend_actor()


@router.post(
    "/{case_id}/recommendations/{recommendation_id}/accept",
    response_model=AcceptActorRecommendation,
    response_model_exclude_none=True,
    description="Accept an Actor recommendation for a Vulnerability Case. (This is a stub implementation.)",
    tags=["Recommend Actors"],
)
async def accept_actor_recommendation_for_case(
    case_id: str, recommendation_id: str
) -> AcceptActorRecommendation:
    """Accept an Actor recommendation for a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.accept_actor_recommendation()


@router.post(
    "/{case_id}/recommendations/{recommendation_id}/reject",
    response_model=RejectActorRecommendation,
    response_model_exclude_none=True,
    description="Reject an Actor recommendation for a Vulnerability Case. (This is a stub implementation.)",
    tags=["Recommend Actors"],
)
async def reject_actor_recommendation_for_case(
    case_id: str, recommendation_id: str
) -> RejectActorRecommendation:
    """Reject an Actor recommendation for a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.reject_actor_recommendation()


# Offer methods
@router.post(
    "/{case_id}/offers/{offer_id}/accept",
    response_model=AcceptCaseOwnershipTransfer,
    response_model_exclude_none=True,
    summary="Accept Case Offer",
    description="Accepts a case offer by an actor.",
    tags=[
        "Case Ownership Transfers",
    ],
)
def accept_case_offer(id: str, offer_id: str) -> AcceptCaseOwnershipTransfer:
    """Accepts a case offer by an actor."""
    return vocab_examples.accept_case_ownership_transfer()


# reject a case offer by an actor
@router.post(
    "/{case_id}/offers/{offer_id}/reject",
    response_model=RejectCaseOwnershipTransfer,
    response_model_exclude_none=True,
    summary="Reject Case Offer",
    description="Rejects a case offer by an actor.",
    tags=[
        "Case Ownership Transfers",
    ],
)
def reject_case_offer(id: str, offer_id: str) -> RejectCaseOwnershipTransfer:
    """Rejects a case offer by an actor."""
    return vocab_examples.reject_case_ownership_transfer()


# Invitation methods


@router.post(
    "/{case_id}/invitations/{invitation_id}/accept",
    response_model=RmAcceptInviteToCase,
    response_model_exclude_none=True,
    description="Accept an invitation to a Vulnerability Case. (This is a stub implementation.)",
    summary="Accept Invitation to Case",
    tags=["Invite Actor to Case"],
)
async def accept_invitation_to_case(
    case_id: str, invitation_id: str
) -> RmAcceptInviteToCase:
    """Accept an invitation to a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.accept_invite_to_case()


@router.post(
    "/{case_id}/invitations/{invitation_id}/reject",
    response_model=RmRejectInviteToCase,
    response_model_exclude_none=True,
    description="Reject an invitation to a Vulnerability Case. (This is a stub implementation.)",
    summary="Reject Invitation to Case",
    tags=["Invite Actor to Case"],
)
async def reject_invitation_to_case(
    case_id: str, invitation_id: str
) -> RmRejectInviteToCase:
    """Reject an invitation to a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.reject_invite_to_case()


# Case status methods


@router.get(
    "/{case_id}/statuses",
    response_model=list[CaseStatus],
    response_model_exclude_none=True,
    description="Get the status history for a Vulnerability Case.",
    tags=["Statuses"],
)
async def get_case_statuses(case_id: str) -> list[CaseStatus]:
    statuses = []
    for _ in range(3):
        statuses.append(vocab_examples.case_status())
    return statuses


@router.get(
    "/statuses/examples",
    response_model=CaseStatus,
    response_model_exclude_none=True,
    description="Get an example Case Status object.",
    tags=["Examples"],
)
async def get_example_case_status() -> CaseStatus:
    """Returns an example CaseStatus object."""
    return vocab_examples.case_status()


@router.post(
    "/{case_id}/statuses",
    response_model=CreateCaseStatus,
    response_model_exclude_none=True,
    description="Create a new Case Status for a Vulnerability Case. (This is a stub implementation.)",
    tags=["Statuses"],
)
async def create_case_status(
    case_id: str, status: CaseStatus
) -> CreateCaseStatus:
    """Creates a new CaseStatus for a VulnerabilityCase."""
    return vocab_examples.create_case_status()


@router.post(
    "/{case_id}/statuses/{status_id}",
    response_model=AddStatusToCase,
    response_model_exclude_none=True,
    description="Add an existing status to a Vulnerability Case. (This is a stub implementation)",
    tags=["Statuses"],
)
async def add_status_to_case(case_id: str, status_id: str) -> AddStatusToCase:
    """Adds an existing status to a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.add_status_to_case()


@router.get(
    "/participants/examples",
    response_model=CaseParticipant,
    response_model_exclude_none=True,
    description="Get an example Case Participant object.",
    tags=["Examples"],
)
async def get_example_participant() -> CaseParticipant:
    """Returns an example CaseParticipant object."""
    return vocab_examples.case_participant()


@router.get(
    "/participants/statuses/examples",
    response_model=ParticipantStatus,
    response_model_exclude_none=True,
    description="Get an example Participant Status object.",
    tags=["Examples"],
)
async def get_example_participant_status() -> ParticipantStatus:
    """Returns an example ParticipantStatus object."""
    return vocab_examples.participant_status()


# this just provides an example EmbargoEvent object
# without having to know a case ID
@router.get(
    "/embargoes/examples",
    response_model=EmbargoEvent,
    response_model_exclude_none=True,
    description="Get an example Embargo Event object.",
    tags=["Examples", "Embargoes"],
)
async def get_example_embargo() -> EmbargoEvent:
    """Returns an example EmbargoEvent object."""
    return vocab_examples.embargo_event()
