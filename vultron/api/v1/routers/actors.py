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

import random

from fastapi import APIRouter

from vultron.as_vocab.activities.case import (
    OfferCaseOwnershipTransfer,
    AcceptCaseOwnershipTransfer,
    RejectCaseOwnershipTransfer,
    RmInviteToCase,
)
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.scripts import vocab_examples

router = APIRouter()


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


@router.get(
    "/example",
    response_model=as_Actor,
    response_model_exclude_none=True,
    description="Get an example Actor object.",
)
def get_example_actor() -> as_Actor:
    """
    Get an example Actor object
    """
    options = [
        vocab_examples.finder,
        vocab_examples.vendor,
        vocab_examples.coordinator,
    ]
    func = random.choice(options)

    return func()


@router.post(
    "/{id}/cases/offer",
    response_model=OfferCaseOwnershipTransfer,
    response_model_exclude_none=True,
    summary="Offer Case to Actor",
    description="Offers a Vulnerability Case to an Actor.",
)
def offer_case_to_actor(
    id: str, case: VulnerabilityCase
) -> OfferCaseOwnershipTransfer:
    """Offers a Vulnerability Case to an Actor."""
    return vocab_examples.offer_case_ownership_transfer()


@router.put(
    "/{id}/offers/{offer_id}/accept",
    response_model=AcceptCaseOwnershipTransfer,
    response_model_exclude_none=True,
    summary="Accept Case Offer",
    description="Accepts a case offer by an actor.",
)
def accept_case_offer(id: str, offer_id: str) -> AcceptCaseOwnershipTransfer:
    """Accepts a case offer by an actor."""
    return vocab_examples.accept_case_ownership_transfer()


# reject a case offer by an actor
@router.put(
    "/{id}/offers/{offer_id}/reject",
    response_model=RejectCaseOwnershipTransfer,
    response_model_exclude_none=True,
    summary="Reject Case Offer",
    description="Rejects a case offer by an actor.",
)
def reject_case_offer(id: str, offer_id: str) -> RejectCaseOwnershipTransfer:
    """Rejects a case offer by an actor."""
    return vocab_examples.reject_case_ownership_transfer()


@router.post(
    "/{id}/invitations",
    response_model=RmInviteToCase,
    response_model_exclude_none=True,
    summary="Invite Actor to Case",
    description="Invites an Actor to a Vulnerability Case.",
)
def invite_actor_to_case(id: str, case: VulnerabilityCase) -> RmInviteToCase:
    """Invites an Actor to a Vulnerability Case."""
    return vocab_examples.invite_to_case()
