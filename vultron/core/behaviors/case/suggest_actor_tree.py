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
"""

import logging
from typing import cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.actor import EmitInviteActorToCaseNode
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.ports.case_persistence import CaseOutboxPersistence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared emit nodes
# ---------------------------------------------------------------------------


class EmitOfferCaseParticipantToOwnerNode(DataLayerAction):
    """Transform Offer(Actor, Case) → Offer(CaseParticipant) and DM Case Owner.

    Uses ``trigger_activity_factory.offer_actor_to_case()`` with the
    recommender_id, recommended_id, default roles, case_id, and case owner id.
    The original offer ID is carried in the ``origin`` field so the Case Owner
    can trace the causal chain (CM-16-004).

    Returns SUCCESS on success, FAILURE if any required dependency is missing.
    """

    def __init__(
        self,
        recommendation_id: str,
        recommender_id: str,
        recommended_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.recommendation_id = recommendation_id
        self.recommender_id = recommender_id
        self.recommended_id = recommended_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        factory = self.trigger_activity_factory
        if factory is None:
            self.feedback_message = (
                "trigger_activity_factory not in blackboard"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        try:
            case_obj = self.datalayer.read(self.case_id)
            raw_owner = getattr(case_obj, "attributed_to", None)
            owner_id = getattr(raw_owner, "id_", raw_owner) or self.actor_id
            activity_id, _ = factory.offer_actor_to_case(
                recommender_id=self.recommender_id,
                recommended_id=self.recommended_id,
                case_id=self.case_id,
                actor=self.actor_id,
                origin=self.recommendation_id,
                to=[owner_id],
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            self.logger.info(
                "%s: queued Offer(CaseParticipant) '%s' to Case Owner outbox"
                " for case '%s'",
                self.name,
                activity_id,
                self.case_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.feedback_message = (
                f"EmitOfferCaseParticipantToOwner failed: {e}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE


class EmitAcceptActorRecommendationNode(DataLayerAction):
    """Queue AcceptActorRecommendation to the original recommender.

    Used after the Case Owner accepts Offer(CaseParticipant) (CM-16-006 step 3).
    The ``in_reply_to`` field is set to the original recommender's offer ID
    (carried in the Case Owner's Accept via the ``origin`` field of the
    transformed Offer) so the recommender can correlate the response.
    """

    def __init__(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.recommender_id = recommender_id
        self.recommendation_id = recommendation_id
        self.recommended_id = recommended_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        factory = self.trigger_activity_factory
        if factory is None:
            self.feedback_message = (
                "trigger_activity_factory not in blackboard"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        try:
            activity_id, _ = factory.emit_accept_actor_recommendation(
                recommender_id=self.recommender_id,
                recommendation_id=self.recommendation_id,
                recommended_id=self.recommended_id,
                case_id=self.case_id,
                actor=self.actor_id,
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            self.logger.info(
                "%s: queued AcceptActorRecommendation to '%s' for case '%s'",
                self.name,
                self.recommender_id,
                self.case_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.feedback_message = (
                f"EmitAcceptActorRecommendation failed: {e}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE


class EmitRejectActorRecommendationNode(DataLayerAction):
    """Queue RejectActorRecommendation to the original recommender.

    Used after the Case Owner rejects Offer(CaseParticipant) (CM-16-007 step 3).
    """

    def __init__(
        self,
        recommender_id: str,
        recommendation_id: str,
        recommended_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.recommender_id = recommender_id
        self.recommendation_id = recommendation_id
        self.recommended_id = recommended_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        factory = self.trigger_activity_factory
        if factory is None:
            self.feedback_message = (
                "trigger_activity_factory not in blackboard"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        try:
            activity_id, _ = factory.emit_reject_actor_recommendation(
                recommender_id=self.recommender_id,
                recommendation_id=self.recommendation_id,
                recommended_id=self.recommended_id,
                case_id=self.case_id,
                actor=self.actor_id,
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            self.logger.info(
                "%s: queued RejectActorRecommendation to '%s' for case '%s'",
                self.name,
                self.recommender_id,
                self.case_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.feedback_message = (
                f"EmitRejectActorRecommendation failed: {e}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE


# ---------------------------------------------------------------------------
# BT factory functions
# ---------------------------------------------------------------------------


def create_recommend_actor_to_case_received_tree(
    recommendation_id: str,
    recommender_id: str,
    recommended_id: str,
    case_id: str,
) -> py_trees.composites.Sequence:
    """Received-side BT for Offer(Actor, Case) on the CaseActor inbox.

    Commits a canonical ``CaseLedgerEntry`` for the received Offer
    (CM-16-002), then transforms it to ``Offer(CaseParticipant{actor,
    roles=[VENDOR]}, Case)`` with ``origin=recommendation_id`` and DMs
    it to the Case Owner (CM-16-003, CM-16-004).

    Args:
        recommendation_id: ID of the incoming ``Offer(Actor, Case)`` activity.
        recommender_id: Actor ID of the recommending participant.
        recommended_id: Actor ID of the suggested new participant.
        case_id: ID of the VulnerabilityCase.

    Returns:
        Root ``RecommendActorToCaseBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="RecommendActorToCaseBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[
            EmitOfferCaseParticipantToOwnerNode(
                recommendation_id=recommendation_id,
                recommender_id=recommender_id,
                recommended_id=recommended_id,
                case_id=case_id,
            ),
        ],
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
    "EmitOfferCaseParticipantToOwnerNode",
    "EmitAcceptActorRecommendationNode",
    "EmitRejectActorRecommendationNode",
    "create_recommend_actor_to_case_received_tree",
    "create_accept_actor_recommendation_received_tree",
    "create_reject_actor_recommendation_received_tree",
]
