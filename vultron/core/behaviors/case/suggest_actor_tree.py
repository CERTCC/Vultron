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

"""Received-side BT factories for the suggest-actor workflow (CaseActor inbox).

Three factories correspond to the three received-side protocol events defined
in ADR-0026/CM-16:

- :func:`create_recommend_actor_to_case_received_tree`  — CaseActor handles
  ``Offer(Actor, Case)`` from a recommending participant (CM-16-001..004).
- :func:`create_accept_actor_recommendation_received_tree` — CaseActor handles
  ``Accept(Offer(CaseParticipant))`` from the Case Owner (CM-16-006).
- :func:`create_reject_actor_recommendation_received_tree` — CaseActor handles
  ``Reject(Offer(CaseParticipant))`` from the Case Owner (CM-16-007).

All three trees route through the CaseActor inbox per ADR-0021/ADR-0026 and
use :func:`~vultron.core.behaviors.case.nodes.lifecycle.create_receive_activity_tree`
to enforce CLP-10-006 ordering (ledger commit before effect nodes).

BT leaf nodes for this workflow are in the
:mod:`vultron.core.behaviors.case.nodes.suggest_actor` subpackage.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.actor import (
    EmitInviteActorToCaseNode,
    EvaluateDefaultRolesNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.case.nodes.suggest_actor import (
    ActorAlreadyParticipantNode,
    EmitAcceptActorRecommendationNode,
    EmitNoteDuplicateRecommendationToOwnerNode,
    EmitOfferCaseParticipantToOwnerNode,
    EmitRejectActorRecommendationNode,
    InviteInFlightNode,
    PendingOfferCaseParticipantNode,
)

logger = logging.getLogger(__name__)


def create_receive_offer_case_participant_tree(
    case_id: str,
) -> py_trees.composites.Sequence:
    """Received-side BT for Offer(CaseParticipant) on the Case Owner inbox.

    Commits a canonical ``CaseLedgerEntry`` for the received
    ``Offer(CaseParticipant)`` (CM-16-003/CM-16-004, ADR-0026). No effect
    nodes are added here — the Case Owner's decision to Accept or Reject is
    a separate outbound activity.

    Args:
        case_id: ID of the VulnerabilityCase.

    Returns:
        Root ``ReceiveOfferCaseParticipantBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="ReceiveOfferCaseParticipantBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[],
    )


def create_recommend_actor_to_case_received_tree(
    recommendation_id: str,
    recommender_id: str,
    recommended_id: str,
    case_id: str,
    offer_content: str | None = None,
) -> py_trees.composites.Sequence:
    """Received-side BT for Offer(Actor, Case) on the CaseActor inbox.

    Commits a canonical ``CaseLedgerEntry`` for the received Offer
    (CM-16-002), then routes to one of four branches via a Selector:

    1. **AC-7b** — already participant: auto-accept to recommender (CM-16-009).
    2. **AC-7a** — invite in-flight: auto-accept to recommender (CM-16-009).
    3. **AC-6** — pending Case Owner decision: send Note DM, no second Offer
       (CM-16-008).
    4. **Fresh path** — evaluate default roles and forward
       ``Offer(CaseParticipant)`` to the Case Owner (CM-16-003, CM-16-004).

    Tree structure::

        RecommendActorToCaseBT (Sequence, memory=False)
        ├── GuardedCommitCaseLedgerEntryBT       — record receipt (CLP-10-006)
        └── DuplicateOrFreshSelector (Selector, memory=False)
            ├── AC-7b: Sequence(ActorAlreadyParticipantNode,
            │                   EmitAcceptActorRecommendationNode)
            ├── AC-7a: Sequence(InviteInFlightNode,
            │                   EmitAcceptActorRecommendationNode)
            ├── AC-6:  Sequence(PendingOfferCaseParticipantNode,
            │                   EmitNoteDuplicateRecommendationToOwnerNode)
            └── Fresh: Sequence(EvaluateDefaultRolesNode,
                                EmitOfferCaseParticipantToOwnerNode)

    Args:
        recommendation_id: ID of the incoming ``Offer(Actor, Case)`` activity.
        recommender_id: Actor ID of the recommending participant.
        recommended_id: Actor ID of the suggested new participant.
        case_id: ID of the VulnerabilityCase.
        offer_content: Optional ``content`` field from the inbound Offer
            activity; forwarded to the duplicate-recommendation Note per
            CM-16-008.

    Returns:
        Root ``RecommendActorToCaseBT`` Sequence node.
    """
    ac7b_already_participant = py_trees.composites.Sequence(
        name="AC7b_AlreadyParticipant",
        memory=False,
        children=[
            ActorAlreadyParticipantNode(
                recommended_id=recommended_id,
                case_id=case_id,
            ),
            EmitAcceptActorRecommendationNode(
                recommender_id=recommender_id,
                recommendation_id=recommendation_id,
                recommended_id=recommended_id,
                case_id=case_id,
            ),
        ],
    )

    ac7a_invite_in_flight = py_trees.composites.Sequence(
        name="AC7a_InviteInFlight",
        memory=False,
        children=[
            InviteInFlightNode(
                recommended_id=recommended_id,
                case_id=case_id,
            ),
            EmitAcceptActorRecommendationNode(
                recommender_id=recommender_id,
                recommendation_id=recommendation_id,
                recommended_id=recommended_id,
                case_id=case_id,
            ),
        ],
    )

    ac6_pending_offer = py_trees.composites.Sequence(
        name="AC6_PendingOffer",
        memory=False,
        children=[
            PendingOfferCaseParticipantNode(
                recommended_id=recommended_id,
                case_id=case_id,
            ),
            EmitNoteDuplicateRecommendationToOwnerNode(
                recommendation_id=recommendation_id,
                recommender_id=recommender_id,
                recommended_id=recommended_id,
                case_id=case_id,
                offer_content=offer_content,
            ),
        ],
    )

    fresh_path = py_trees.composites.Sequence(
        name="FreshRecommendation",
        memory=False,
        children=[
            EvaluateDefaultRolesNode(
                suggested_actor_id=recommended_id,
                case_id=case_id,
                recommendation_id=recommendation_id,
            ),
            EmitOfferCaseParticipantToOwnerNode(
                recommendation_id=recommendation_id,
                recommender_id=recommender_id,
                recommended_id=recommended_id,
                case_id=case_id,
            ),
        ],
    )

    duplicate_or_fresh_selector = py_trees.composites.Selector(
        name="DuplicateOrFreshSelector",
        memory=False,
        children=[
            ac7b_already_participant,
            ac7a_invite_in_flight,
            ac6_pending_offer,
            fresh_path,
        ],
    )

    return create_receive_activity_tree(
        name="RecommendActorToCaseBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[duplicate_or_fresh_selector],
    )


def create_accept_actor_recommendation_received_tree(
    recommendation_id: str,
    recommender_id: str,
    invitee_id: str,
    case_id: str,
) -> py_trees.composites.Sequence:
    """Received-side BT for Accept(Offer(CaseParticipant)) on the CaseActor inbox.

    Commits a canonical ``CaseLedgerEntry`` (CM-16-006 step 1), then fans
    out: sends ``AcceptActorRecommendation`` to the original recommender
    (CM-16-006 step 3) and ``Invite(CaseStub+embargo+roles)`` to the
    invitee (CM-16-006 step 4, CM-17).

    Args:
        recommendation_id: ID of the original ``Offer(Actor, Case)`` from the
            recommender (carried in the ``origin`` field of the transformed Offer).
        recommender_id: Actor ID of the original recommender.
        invitee_id: Actor ID of the suggested new participant.
        case_id: ID of the VulnerabilityCase.

    Returns:
        Root ``AcceptActorRecommendationBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="AcceptActorRecommendationBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[
            EmitAcceptActorRecommendationNode(
                recommender_id=recommender_id,
                recommendation_id=recommendation_id,
                recommended_id=invitee_id,
                case_id=case_id,
            ),
            EmitInviteActorToCaseNode(
                invitee_id=invitee_id,
                case_id=case_id,
                case_actor_id=None,
            ),
        ],
    )


def create_reject_actor_recommendation_received_tree(
    recommendation_id: str,
    recommender_id: str,
    recommended_id: str,
    case_id: str,
) -> py_trees.composites.Sequence:
    """Received-side BT for Reject(Offer(CaseParticipant)) on the CaseActor inbox.

    Commits a canonical ``CaseLedgerEntry`` (CM-16-007 step 1), then sends
    ``RejectActorRecommendation`` to the original recommender
    (CM-16-007 step 3).

    Args:
        recommendation_id: ID of the original ``Offer(Actor, Case)`` from the
            recommender (carried in the ``origin`` field of the transformed Offer).
        recommender_id: Actor ID of the original recommender.
        recommended_id: Actor ID of the suggested new participant.
        case_id: ID of the VulnerabilityCase.

    Returns:
        Root ``RejectActorRecommendationBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="RejectActorRecommendationBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[
            EmitRejectActorRecommendationNode(
                recommender_id=recommender_id,
                recommendation_id=recommendation_id,
                recommended_id=recommended_id,
                case_id=case_id,
            ),
        ],
    )


__all__ = [
    # node classes live in nodes.suggest_actor; re-exported here for backward compat
    "ActorAlreadyParticipantNode",
    "EmitAcceptActorRecommendationNode",
    "EmitNoteDuplicateRecommendationToOwnerNode",
    "EmitOfferCaseParticipantToOwnerNode",
    "EmitRejectActorRecommendationNode",
    "InviteInFlightNode",
    "PendingOfferCaseParticipantNode",
    "create_accept_actor_recommendation_received_tree",
    "create_receive_offer_case_participant_tree",
    "create_recommend_actor_to_case_received_tree",
    "create_reject_actor_recommendation_received_tree",
]
