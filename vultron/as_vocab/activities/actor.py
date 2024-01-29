#!/usr/bin/env python
#  Copyright (c) 2023-2024 Carnegie Mellon University and Contributors.
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

from dataclasses import dataclass, field
from typing import Optional

from dataclasses_json import LetterCase, config, dataclass_json

from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
)
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RecommendActor(as_Offer):
    """The actor is recommending another actor to a case."""

    as_type: str = field(default="Offer", init=False)
    as_object: Optional[as_Actor | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    target: Optional[VulnerabilityCase | as_Link | str] = field(
        default=None,
        repr=True,
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class AcceptActorRecommendation(as_Accept):
    """The case owner is accepting a recommendation to add an actor to the case.
    Should be followed by an RmInviteToCase activity targeted at the recommended actor.
    """

    as_type: str = field(default="Accept", init=False)
    as_object: Optional[as_Actor | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    target: Optional[VulnerabilityCase | as_Link | str] = field(
        default=None,
        repr=True,
    )


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class RejectActorRecommendation(as_Reject):
    """The case owner is rejecting a recommendation to add an actor to the case."""

    as_type: str = field(default="Reject", init=False)
    as_object: Optional[as_Actor | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )
    target: Optional[VulnerabilityCase | as_Link | str] = field(
        default=None,
        repr=True,
    )
