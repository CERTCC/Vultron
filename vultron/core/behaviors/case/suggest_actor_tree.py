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

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.actor import (
    EmitInviteActorToCaseNode,
    EvaluateDefaultRolesNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models.protocol_pair import (
    INVITE_ACTOR_TO_CASE_REPLY_TYPES,
    OFFER_CASE_PARTICIPANT_REPLY_TYPES,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.states.roles import CVDRole

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared emit nodes
# ---------------------------------------------------------------------------


class EmitOfferCaseParticipantToOwnerNode(DataLayerAction):
    """Transform Offer(Actor, Case) → Offer(CaseParticipant) and DM Case Owner.

    Uses ``trigger_activity_factory.offer_actor_to_case()`` with the
    recommender_id, recommended_id, roles from the blackboard (written by
    :class:`~vultron.core.behaviors.case.nodes.actor.EvaluateDefaultRolesNode`),
    case_id, and case owner id.
    The original offer ID is carried in the ``origin`` field so the Case Owner
    can trace the causal chain (CM-16-004).

    Reads ``suggested_roles_{recommendation_id_segment}`` from the blackboard
    (namespaced per BTND-03-004); falls back to ``[CVDRole.VENDOR]`` when the
    key is absent.

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

    def setup(self, **kwargs) -> None:
        super().setup(**kwargs)
        id_segment = self.recommendation_id.split("/")[-1]
        self.blackboard_key = f"suggested_roles_{id_segment}"
        self.blackboard.register_key(
            key=self.blackboard_key, access=py_trees.common.Access.READ
        )

    def _read_suggested_roles(self) -> list[CVDRole]:
        try:
            roles = self.blackboard.get(self.blackboard_key)
            if isinstance(roles, list) and roles:
                return roles
        except KeyError:
            pass
        return [CVDRole.VENDOR]

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

        roles = self._read_suggested_roles()
        try:
            case_obj = self.datalayer.read(self.case_id)
            raw_owner = getattr(case_obj, "attributed_to", None)
            owner_id = getattr(raw_owner, "id_", raw_owner) or None
            if not owner_id:
                self.feedback_message = (
                    f"case '{self.case_id}' has no attributed_to (Case Owner) "
                    "— cannot address Offer(CaseParticipant)"
                )
                self.logger.error(self.feedback_message)
                return Status.FAILURE
            activity_id, _ = factory.offer_actor_to_case(
                recommender_id=self.recommender_id,
                recommended_id=self.recommended_id,
                case_id=self.case_id,
                actor=self.actor_id,
                origin=self.recommendation_id,
                to=[owner_id],
                roles=roles,
            )
            # Commit a local correlation marker first so duplicate checks work
            # on retry even if the outbox write below fails (CM-16-008/AC-6).
            # disposition="rejected" bypasses canonical-payload validation since
            # Offer(CaseParticipant) is not a canonical ledger event type.
            commit_tree = create_commit_log_entry_tree(
                case_id=self.case_id,
                object_id=self.recommended_id,
                event_type="offer_case_participant",
                disposition="rejected",
            )
            result = BTBridge(
                datalayer=cast(CaseOutboxPersistence, self.datalayer)
            ).execute_with_setup(
                tree=commit_tree,
                actor_id=self.actor_id,
            )
            if result.status != Status.SUCCESS:
                raise RuntimeError(
                    f"ledger correlation commit failed for "
                    f"offer_case_participant/{self.recommended_id}"
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
# Duplicate-detection precondition nodes (CM-16-008, CM-16-009)
# ---------------------------------------------------------------------------


class ActorAlreadyParticipantNode(DataLayerAction):
    """Return SUCCESS if the recommended actor is already a case participant.

    Reads ``VulnerabilityCase.actor_participant_index`` from the DataLayer.
    Returns SUCCESS when ``recommended_id`` is a key in the index (AC-7b,
    CM-16-009).

    Used as the first arm of the duplicate-detection Selector in
    :func:`create_recommend_actor_to_case_received_tree`.
    """

    def __init__(
        self,
        recommended_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.recommended_id = recommended_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE
        case_obj = self.datalayer.read(self.case_id)
        index = getattr(case_obj, "actor_participant_index", {}) or {}
        if self.recommended_id in index:
            self.logger.info(
                "%s: actor '%s' is already a participant in case '%s'",
                self.name,
                self.recommended_id,
                self.case_id,
            )
            return Status.SUCCESS
        return Status.FAILURE


class InviteInFlightNode(DataLayerAction):
    """Return SUCCESS if an Invite to the recommended actor is in-flight.

    Queries the case ledger via ``find_protocol_pair`` with
    ``event_type="invite_actor_to_case"`` and ``object_id=recommended_id``.
    Returns SUCCESS when the pair ``is_pending()`` — i.e., an Invite was
    sent and no Accept/Reject has been recorded (AC-7a, CM-16-009).

    Used as the second arm of the duplicate-detection Selector in
    :func:`create_recommend_actor_to_case_received_tree`.
    """

    def __init__(
        self,
        recommended_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.recommended_id = recommended_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE
        pair = self.datalayer.find_protocol_pair(
            case_id=self.case_id,
            request_event_type="invite_actor_to_case",
            object_id=self.recommended_id,
            reply_event_types=INVITE_ACTOR_TO_CASE_REPLY_TYPES,
        )
        if pair.is_pending():
            self.logger.info(
                "%s: Invite to '%s' is in-flight for case '%s'",
                self.name,
                self.recommended_id,
                self.case_id,
            )
            return Status.SUCCESS
        return Status.FAILURE


class PendingOfferCaseParticipantNode(DataLayerAction):
    """Return SUCCESS if an Offer(CaseParticipant) to the Case Owner is pending.

    Queries the case ledger via ``find_protocol_pair`` with
    ``event_type="offer_case_participant"`` and ``object_id=recommended_id``.
    Returns SUCCESS when the pair ``is_pending()`` — i.e., the CaseActor
    has already forwarded an Offer(CaseParticipant) for this actor and the
    Case Owner has not yet responded (AC-6, CM-16-008).

    Used as the third arm of the duplicate-detection Selector in
    :func:`create_recommend_actor_to_case_received_tree`.
    """

    def __init__(
        self,
        recommended_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.recommended_id = recommended_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE
        pair = self.datalayer.find_protocol_pair(
            case_id=self.case_id,
            request_event_type="offer_case_participant",
            object_id=self.recommended_id,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )
        if pair.is_pending():
            self.logger.info(
                "%s: Offer(CaseParticipant) for '%s' is pending Case Owner "
                "decision in case '%s'",
                self.name,
                self.recommended_id,
                self.case_id,
            )
            return Status.SUCCESS
        return Status.FAILURE


class EmitNoteDuplicateRecommendationToOwnerNode(DataLayerAction):
    """Send a Note DM to the Case Owner noting reinforcing demand.

    Used when a second ``Offer(Actor, Case)`` arrives while a first
    ``Offer(CaseParticipant)`` is still pending the Case Owner's
    Accept/Reject decision (AC-6, CM-16-008).  Sends a
    ``Create(Note)`` + ``Add(Note, Case)`` to the Case Owner without
    issuing a second ``Offer(CaseParticipant)``.
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
            owner_id = getattr(raw_owner, "id_", raw_owner) or None
            if not owner_id:
                self.feedback_message = (
                    f"case '{self.case_id}' has no attributed_to (Case Owner) "
                    "— cannot address duplicate-recommendation Note"
                )
                self.logger.error(self.feedback_message)
                return Status.FAILURE

            actor_segment = self.recommended_id.split("/")[-1]
            content = (
                f"Duplicate actor recommendation: '{self.recommender_id}' "
                f"also recommends actor '{actor_segment}' for case "
                f"'{self.case_id}'.  An Offer(CaseParticipant) is already "
                f"pending your decision (no second offer sent)."
            )
            note_id, _ = factory.create_note(
                name=f"Duplicate recommendation — {actor_segment}",
                content=content,
                context_id=self.case_id,
                attributed_to=self.actor_id,
                in_reply_to=self.recommendation_id,
            )
            activity_id, _ = factory.add_note_to_case(
                note_id=note_id,
                case_id=self.case_id,
                actor=self.actor_id,
                to=[owner_id],
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            self.logger.info(
                "%s: sent duplicate-recommendation Note to Case Owner '%s'"
                " for case '%s'",
                self.name,
                owner_id,
                self.case_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.feedback_message = (
                f"EmitNoteDuplicateRecommendationToOwner failed: {e}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE


# ---------------------------------------------------------------------------
# BT factory functions
# ---------------------------------------------------------------------------


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
