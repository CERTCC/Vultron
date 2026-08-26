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

from typing import ClassVar

from pydantic import Field

from vultron.core.models.actor import CoreActor
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseRef,
)


class _RecommendActorActivity(as_Offer):
    """The actor is recommending another actor to a case.

    Declares ``object_`` in :attr:`inline_required_refs` (DL-08-003) for the
    same reason as ``_RmInviteToCaseActivity``: the recommended actor is a peer,
    so under ADR-0073 the recommender's own store holds no record of it and a
    dehydrated id has nothing to be read back from. Delivery then refuses the
    recommendation for carrying a bare string (AKM-03-001).
    """

    object_: CoreActor | as_Actor = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseRef = None
    # suggested_roles is inherited from as_Offer, aliased there; redeclaring it
    # here would shadow the base field and drop the camelCase alias (#1990).

    inline_required_refs: ClassVar[frozenset[str]] = frozenset({"object_"})


class _AcceptActorRecommendationActivity(as_Accept):
    """The case owner is accepting a recommendation to add an actor to the case.

    - object_: the _RecommendActorActivity offer being accepted (inline typed
      object required — bare string IDs are rejected at construction time)
    Should be followed by an _RmInviteToCaseActivity activity targeted at the recommended actor.
    """

    object_: _RecommendActorActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseRef = None


class _RejectActorRecommendationActivity(as_Reject):
    """The case owner is rejecting a recommendation to add an actor to the case.

    - object_: the _RecommendActorActivity offer being rejected (inline typed
      object required — bare string IDs are rejected at construction time)
    """

    object_: _RecommendActorActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseRef = None


class _OfferCaseParticipantActivity(as_Offer):
    """CaseActor offers a CaseParticipant (with roles) to the Case Owner.

    Transforms the original ``Offer(Actor, Case)`` from a recommending
    participant into this ``Offer(CaseParticipant{actor, roles}, Case)``
    with ``origin`` carrying the original Offer ID for causal traceability
    (CM-16-004, ADR-0026).
    """

    object_: as_CaseParticipant = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseRef = None


class _AcceptCaseParticipantOfferActivity(as_Accept):
    """Case Owner accepts Offer(CaseParticipant) from the CaseActor.

    Routed to the CaseActor inbox (CM-16-006).
    """

    object_: _OfferCaseParticipantActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseRef = None


class _RejectCaseParticipantOfferActivity(as_Reject):
    """Case Owner rejects Offer(CaseParticipant) from the CaseActor.

    Routed to the CaseActor inbox (CM-16-007).
    """

    object_: _OfferCaseParticipantActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_VulnerabilityCaseRef = None


# NOTE: Old non-suffixed names were removed intentionally. Use the
# _RecommendActorActivity / _AcceptActorRecommendationActivity /
# _RejectActorRecommendationActivity class names.
