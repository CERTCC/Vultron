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

from vultron.as_vocab.activities.case import (
    OfferCaseOwnershipTransfer,
    RmInviteToCase,
)
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.scripts import vocab_examples

router = APIRouter(prefix="/actors", tags=["Actors"])


@router.get(
    "/",
    response_model=list[as_Actor],
    response_model_exclude_none=True,
    description="Returns a list of Actor examples.",
)
def get_actors() -> as_Actor:
    finder = vocab_examples.finder()
    vendor = vocab_examples.vendor()
    coordinator = vocab_examples.coordinator()
    actors = [finder, vendor, coordinator]
    return actors


@router.post(
    "/{actor_id}/cases/offers",
    response_model=OfferCaseOwnershipTransfer,
    response_model_exclude_none=True,
    summary="Offer Case to Actor",
    description="Offers a Vulnerability Case to an Actor.",
    tags=["Case Ownership Transfers", "Cases"],
)
def offer_case_to_actor(
    id: str, case: VulnerabilityCase
) -> OfferCaseOwnershipTransfer:
    """Offers a Vulnerability Case to an Actor."""
    return vocab_examples.offer_case_ownership_transfer()


@router.post(
    "/{actor_id}/cases/invitations",
    response_model=RmInviteToCase,
    response_model_exclude_none=True,
    summary="Invite Actor to Case",
    description="Invites an Actor to a Vulnerability Case.",
    tags=["Invite Actor to Case", "Cases"],
)
def invite_actor_to_case(id: str, case: VulnerabilityCase) -> RmInviteToCase:
    """Invites an Actor to a Vulnerability Case."""
    return vocab_examples.invite_to_case()
