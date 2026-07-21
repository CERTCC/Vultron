#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Suggest-actor workflow BT leaf nodes (ADR-0026 / CM-16).

Submodules:

- ``emit``: CaseActor-side emission and state-write nodes
  (``RecordRecommendationRecommenderNode``,
  ``EmitOfferCaseParticipantToOwnerNode``,
  ``EmitAcceptActorRecommendationNode``,
  ``EmitRejectActorRecommendationNode``,
  ``EmitNoteDuplicateRecommendationToOwnerNode``)
- ``accept_offer``: Case Owner owner-side Accept response
  (``EmitAcceptCaseParticipantOfferNode``)
- ``conditions``: Duplicate-detection precondition nodes
  (``ActorAlreadyParticipantNode``,
  ``InviteInFlightNode``,
  ``PendingOfferCaseParticipantNode``)
"""

from vultron.core.behaviors.case.nodes.suggest_actor.accept_offer import (
    EmitAcceptCaseParticipantOfferNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor.conditions import (
    ActorAlreadyParticipantNode,
    InviteInFlightNode,
    PendingOfferCaseParticipantNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor.emit import (
    EmitAcceptActorRecommendationNode,
    EmitNoteDuplicateRecommendationToOwnerNode,
    EmitOfferCaseParticipantToOwnerNode,
    EmitRejectActorRecommendationNode,
    RecordRecommendationRecommenderNode,
)

__all__ = [
    "ActorAlreadyParticipantNode",
    "EmitAcceptActorRecommendationNode",
    "EmitAcceptCaseParticipantOfferNode",
    "EmitNoteDuplicateRecommendationToOwnerNode",
    "EmitOfferCaseParticipantToOwnerNode",
    "EmitRejectActorRecommendationNode",
    "InviteInFlightNode",
    "PendingOfferCaseParticipantNode",
    "RecordRecommendationRecommenderNode",
]
