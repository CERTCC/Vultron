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

"""Outbound activity emission nodes for the suggest-actor workflow (CM-16).

Node classes:

- :class:`RecordRecommendationRecommenderNode` — writes
  ``recommendation_id → recommender_id`` into
  ``VulnerabilityCase.recommendation_recommender_index`` (ADR-0035 DL-06-002).
- :class:`EmitOfferCaseParticipantToOwnerNode` — transforms
  ``Offer(Actor, Case)`` into ``Offer(CaseParticipant)`` and DMs the Case Owner
  (CM-16-004).
- :class:`EmitAcceptActorRecommendationNode` — queues
  ``AcceptActorRecommendation`` to the original recommender (CM-16-006).
- :class:`EmitRejectActorRecommendationNode` — queues
  ``RejectActorRecommendation`` to the original recommender (CM-16-007).
- :class:`EmitNoteDuplicateRecommendationToOwnerNode` — sends a
  ``Create(Note)`` + ``Add(Note, Case)`` to the Case Owner when a duplicate
  recommendation arrives (CM-16-008).
"""

from typing import cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.enums.roles import CVDRole


class RecordRecommendationRecommenderNode(DataLayerAction):
    """Write recommendation_id → recommender_id into core case state.

    Runs as the first effect node in ``RecommendActorToCaseBT`` so downstream
    Accept/Reject use cases can look up the recommender without re-reading the
    stored wire Offer (ADR-0035 DL-06-002, CLP-10-005).

    Idempotent: no-op when the index already holds the correct mapping.
    Returns SUCCESS unconditionally so the tree continues even when the case
    cannot be found (the subsequent routing nodes will handle that failure).
    """

    def __init__(
        self,
        recommendation_id: str,
        recommender_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.recommendation_id = recommendation_id
        self.recommender_id = recommender_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None:
            return Status.SUCCESS

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            return Status.SUCCESS

        if (
            case.recommendation_recommender_index.get(self.recommendation_id)
            != self.recommender_id
        ):
            case.recommendation_recommender_index[self.recommendation_id] = (
                self.recommender_id
            )
            self.datalayer.save(case)
            self.logger.debug(
                "%s: recorded recommender '%s' for recommendation '%s'"
                " in case '%s'",
                self.name,
                self.recommender_id,
                self.recommendation_id,
                self.case_id,
            )

        return Status.SUCCESS


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
            if isinstance(roles, list):
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
        if not roles:
            self.feedback_message = (
                f"suggested_roles for actor '{self.recommended_id}' is empty "
                "— cannot emit Offer(CaseParticipant) without at least one role"
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


class EmitNoteDuplicateRecommendationToOwnerNode(DataLayerAction):
    """Send a Note DM to the Case Owner noting reinforcing demand.

    Used when a second ``Offer(Actor, Case)`` arrives while a first
    ``Offer(CaseParticipant)`` is still pending the Case Owner's
    Accept/Reject decision (AC-6, CM-16-008).  Sends a
    ``Create(Note)`` + ``Add(Note, Case)`` to the Case Owner without
    issuing a second ``Offer(CaseParticipant)``.

    When ``offer_content`` is provided (non-None, non-empty), it is appended
    to the Note body per CM-16-008's requirement to forward the incoming
    Offer's ``content`` field to the Case Owner.
    """

    def __init__(
        self,
        recommendation_id: str,
        recommender_id: str,
        recommended_id: str,
        case_id: str,
        offer_content: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.recommendation_id = recommendation_id
        self.recommender_id = recommender_id
        self.recommended_id = recommended_id
        self.case_id = case_id
        self.offer_content = (
            (offer_content.strip() or None) if offer_content else None
        )

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
            if self.offer_content:
                content = (
                    f"{content}\n\nRecommender note: {self.offer_content}"
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


__all__ = [
    "EmitAcceptActorRecommendationNode",
    "EmitNoteDuplicateRecommendationToOwnerNode",
    "EmitOfferCaseParticipantToOwnerNode",
    "EmitRejectActorRecommendationNode",
]
