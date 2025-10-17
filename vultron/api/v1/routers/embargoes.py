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

from vultron.as_vocab.activities.embargo import (
    EmProposeEmbargo,
    RemoveEmbargoFromCase,
    AnnounceEmbargo,
    ActivateEmbargo,
    AddEmbargoToCase,
    EmRejectEmbargo,
    EmAcceptEmbargo,
)
from vultron.as_vocab.objects.embargo_event import EmbargoEvent
from vultron.scripts import vocab_examples

router = APIRouter(prefix="/cases/{case_id}/embargoes", tags=["Embargoes"])


@router.post(
    "/",
    response_model=AddEmbargoToCase,
    response_model_exclude_none=True,
    summary="Add Embargo to Case (Case Owners Only)",
    description="Add an embargo to a Vulnerability Case. (This is a stub implementation)",
    tags=["Embargoes"],
)
async def add_embargo_to_case(
    case_id: str, embargo: EmbargoEvent
) -> AddEmbargoToCase:
    """Add an embargo to a VulnerabilityCase. This endpoint is available to case owners only. (This is a stub implementation.)"""
    return vocab_examples.add_embargo_to_case()


@router.post(
    "/propose",
    response_model=EmProposeEmbargo,
    response_model_exclude_none=True,
    summary="Propose Embargo for Case (Any Case Participant)",
    description="Propose an embargo for a Vulnerability Case. (This is a stub implementation)",
    tags=["Embargoes"],
)
async def propose_embargo_for_case(
    case_id: str, embargo: EmbargoEvent
) -> EmProposeEmbargo:
    """Propose an embargo for a VulnerabilityCase. This endpoint is available to any case participant. (This is a stub implementation.)"""
    return vocab_examples.propose_embargo()


# TODO how to model choose_preferred_embargo?


# accept embargo
@router.post(
    "/{embargo_id}/accept",
    response_model=EmAcceptEmbargo,
    response_model_exclude_none=True,
    description="Accept an embargo for a Vulnerability Case. (This is a stub implementation)",
    tags=["Embargoes"],
)
async def accept_embargo_for_case(
    case_id: str, embargo_id: str
) -> EmAcceptEmbargo:
    """Accept an embargo for a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.accept_embargo()


# reject embargo
@router.post(
    "/{embargo_id}/reject",
    response_model=EmRejectEmbargo,
    response_model_exclude_none=True,
    description="Reject an embargo for a Vulnerability Case. (This is a stub implementation)",
    tags=["Embargoes"],
)
async def reject_embargo_for_case(
    case_id: str, embargo_id: str
) -> EmRejectEmbargo:
    """Reject an embargo for a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.reject_embargo()


# activate embargo
@router.post(
    "/{embargo_id}/activate",
    response_model=ActivateEmbargo,
    response_model_exclude_none=True,
    description="Activate an embargo for a Vulnerability Case. (This is a stub implementation)",
    tags=["Embargoes"],
)
async def activate_embargo_for_case(
    case_id: str, embargo_id: str
) -> ActivateEmbargo:
    """Activate an embargo for a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.activate_embargo()


# announce embargo
@router.post(
    "/announce",
    response_model=AnnounceEmbargo,
    response_model_exclude_none=True,
    description="Announce the active embargo for a Vulnerability Case. (This is a stub implementation)",
    tags=["Embargoes"],
)
async def announce_embargo_for_case(
    case_id: str, embargo_id: str
) -> AnnounceEmbargo:
    """Announce an embargo for a VulnerabilityCase. (This is a stub implementation.)"""
    return vocab_examples.announce_embargo()


# remove embargo from case
@router.delete(
    "/{embargo_id}",
    response_model=RemoveEmbargoFromCase,
    response_model_exclude_none=True,
    summary="Remove Embargo from Case (Case Owners Only)",
    description="Remove an embargo from a Vulnerability Case. (This is a stub implementation)",
    tags=["Embargoes"],
)
async def remove_embargo_from_case(
    case_id: str, embargo_id: str
) -> RemoveEmbargoFromCase:
    """Remove an embargo from a VulnerabilityCase. This endpoint is available to case owners only. (This is a stub implementation.)"""
    return vocab_examples.remove_embargo()
