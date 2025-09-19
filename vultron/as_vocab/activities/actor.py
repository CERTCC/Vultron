#!/usr/bin/env python
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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
"""
Provides Vultron ActivityStreams Activities related to Actors
"""

from typing import Literal

from pydantic import Field

from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
)
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase


class RecommendActor(as_Offer):
    """The actor is recommending another actor to a case."""

    as_type: Literal["Offer"] = "Offer"
    as_object: as_Actor | as_Link | str | None = Field(
        default=None, alias="object"
    )
    target: VulnerabilityCase | as_Link | str | None = None


class AcceptActorRecommendation(as_Accept):
    """The case owner is accepting a recommendation to add an actor to the case.
    Should be followed by an RmInviteToCase activity targeted at the recommended actor.
    """

    as_type: Literal["Accept"] = "Accept"
    as_object: as_Actor | as_Link | str | None = Field(
        default=None, alias="object"
    )
    target: VulnerabilityCase | as_Link | str | None = None


class RejectActorRecommendation(as_Reject):
    """The case owner is rejecting a recommendation to add an actor to the case."""

    as_type: Literal["Reject"] = "Reject"
    as_object: as_Actor | as_Link | str | None = Field(
        default=None, alias="object"
    )
    target: VulnerabilityCase | as_Link | str | None = None
