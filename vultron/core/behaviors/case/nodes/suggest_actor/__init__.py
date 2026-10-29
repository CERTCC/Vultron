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

- ``emit``: CaseActor-side nodes addressing the *Case Owner* — state writes and
  the offer it must decide on
  (``RecordRecommendationRecommenderNode``,
  ``EmitOfferCaseParticipantToOwnerNode``,
  ``EmitNoteDuplicateRecommendationToOwnerNode``)
- ``emit_response``: the answer back to the *recommender* once the owner has
  decided
  (``EmitAcceptActorRecommendationNode``,
  ``EmitRejectActorRecommendationNode``)
- ``accept_offer``: Case Owner owner-side Accept and Reject responses
  (``EmitAcceptCaseParticipantOfferNode``,
  ``EmitRejectCaseParticipantOfferNode``)
- ``conditions``: Duplicate-detection precondition nodes
  (``ActorAlreadyParticipantNode``,
  ``InviteInFlightNode``,
  ``PendingOfferCaseParticipantNode``)
- ``recorded_offer``: the recorded Offer a Case Owner's answer names, looked
  up as a precondition guard (``RequireRecordedOfferAnswerNode``) and read by
  the answer's later nodes (``RecordedOfferAnswerInputMixin``)
- ``recorded_invite``: the stub Invite and inert record the Case Owner's
  Accept makes, from the recorded Offer
  (``EmitRecordedInviteNode``, ``SeatRecordedInviteeNode``)
"""

from vultron.core.behaviors.case.nodes.suggest_actor.accept_offer import (
    EmitAcceptCaseParticipantOfferNode,
    EmitRejectCaseParticipantOfferNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor.conditions import (
    AcceptedInviteeIsNotRemovedNode,
    ActorAlreadyParticipantNode,
    InviteInFlightNode,
    PendingOfferCaseParticipantNode,
    SuggestedActorIsInvitableNode,
    SuggestedActorIsNotRemovedNode,
    case_manager_admits_accepted_invitee_guard,
    case_manager_admits_suggested_actor_guard,
    case_manager_requires_recorded_rejection_guard,
)
from vultron.core.behaviors.case.nodes.suggest_actor.emit import (
    EmitNoteDuplicateRecommendationToOwnerNode,
    EmitOfferCaseParticipantToOwnerNode,
    RecordRecommendationRecommenderNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor.emit_response import (
    EmitAcceptActorRecommendationNode,
    EmitAcceptRecordedRecommendationNode,
    EmitRejectActorRecommendationNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor.recorded_invite import (
    EmitRecordedInviteNode,
    SeatRecordedInviteeNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor.recorded_offer import (
    RecordedOfferAnswer,
    RequireRecordedOfferAnswerNode,
)

__all__ = [
    "ActorAlreadyParticipantNode",
    "AcceptedInviteeIsNotRemovedNode",
    "RecordedOfferAnswer",
    "RequireRecordedOfferAnswerNode",
    "SuggestedActorIsNotRemovedNode",
    "SuggestedActorIsInvitableNode",
    "case_manager_admits_accepted_invitee_guard",
    "case_manager_admits_suggested_actor_guard",
    "case_manager_requires_recorded_rejection_guard",
    "EmitAcceptActorRecommendationNode",
    "EmitAcceptRecordedRecommendationNode",
    "EmitRecordedInviteNode",
    "EmitAcceptCaseParticipantOfferNode",
    "EmitRejectCaseParticipantOfferNode",
    "EmitNoteDuplicateRecommendationToOwnerNode",
    "EmitOfferCaseParticipantToOwnerNode",
    "EmitRejectActorRecommendationNode",
    "InviteInFlightNode",
    "PendingOfferCaseParticipantNode",
    "RecordRecommendationRecommenderNode",
    "SeatRecordedInviteeNode",
]
