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

from pydantic import Field

from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCaseRef,
)


class RecommendActorActivity(as_Offer):
    """The actor is recommending another actor to a case."""

    object_: as_Actor | None = Field(
        default=None, validation_alias="object", serialization_alias="object"
    )
    target: VulnerabilityCaseRef = None


class AcceptActorRecommendationActivity(as_Accept):
    """The case owner is accepting a recommendation to add an actor to the case.

    - object_: the RecommendActorActivity offer being accepted (inline typed
      object required — bare string IDs are rejected at construction time)
    Should be followed by an RmInviteToCaseActivity activity targeted at the recommended actor.
    """

    object_: RecommendActorActivity | None = Field(
        default=None, validation_alias="object", serialization_alias="object"
    )
    target: VulnerabilityCaseRef = None


class RejectActorRecommendationActivity(as_Reject):
    """The case owner is rejecting a recommendation to add an actor to the case.

    - object_: the RecommendActorActivity offer being rejected (inline typed
      object required — bare string IDs are rejected at construction time)
    """

    object_: RecommendActorActivity | None = Field(
        default=None, validation_alias="object", serialization_alias="object"
    )
    target: VulnerabilityCaseRef = None


# NOTE: Old non-suffixed names were removed intentionally. Use the
# RecommendActorActivity / AcceptActorRecommendationActivity /
# RejectActorRecommendationActivity class names.
