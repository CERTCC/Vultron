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

"""Duplicate-detection precondition nodes for the suggest-actor workflow (CM-16).

Node classes:

- :class:`ActorAlreadyParticipantNode` — returns SUCCESS when the recommended
  actor is already a case participant (CM-16-009 / AC-7b).
- :class:`InviteInFlightNode` — returns SUCCESS when an Invite to the
  recommended actor is in-flight (CM-16-009 / AC-7a).
- :class:`PendingOfferCaseParticipantNode` — returns SUCCESS when an
  Offer(CaseParticipant) to the Case Owner is already pending (CM-16-008 /
  AC-6).

The admission guards that refuse a recommendation before its commit live in
:mod:`~vultron.core.behaviors.case.nodes.suggest_actor.admission`.
"""

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.suggest_actor.emit import (
    offer_case_participant_id,
)
from vultron.core.behaviors.case.nodes.suggest_actor.pending_request import (
    invitee,
    offered_participant_actor,
    request_naming_actor_is_pending,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.protocol_pair import (
    INVITE_ACTOR_TO_CASE_REPLY_TYPES,
    OFFER_CASE_PARTICIPANT_REPLY_TYPES,
)
from vultron.errors import VultronWiringError


class ActorAlreadyParticipantNode(DataLayerActionWithPorts):
    """Return SUCCESS if the recommended actor is already a joined case participant.

    Reads ``VulnerabilityCase.actor_participant_index`` from the DataLayer.
    Returns SUCCESS when ``recommended_id`` is in the index AND the participant
    record has ``joined=True`` (AC-7b, CM-16-009).

    An *inert* participant created at invite-send time (``joined=False``,
    ADR-0114, CM-11-006) is treated as absent so the re-invite flow can proceed
    (CM-11-015 precedent).

    Used as the first arm of the duplicate-detection Selector in
    :func:`~vultron.core.behaviors.case.suggest_actor_tree.create_recommend_actor_to_case_received_tree`.
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
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        # Regime 3 (ADR-0087): a condition testing whether an actor is *already*
        # a participant. An absent case ⇒ empty index ⇒ recommended not present
        # ⇒ FAILURE ("not already a participant"), which is the correct answer
        # here, so the graceful ``getattr`` default is intentional (allowlist).
        case_obj = self.datalayer.read_case(self.case_id)
        index = getattr(case_obj, "actor_participant_index", {}) or {}
        if self.recommended_id not in index:
            return Status.FAILURE
        # An inert record (joined=False) is not a true participant yet;
        # return FAILURE so the re-invite / fresh-invite path can proceed.
        participant_id = index[self.recommended_id]
        participant = self.datalayer.read(participant_id)
        if isinstance(participant, CaseParticipant) and not participant.joined:
            self.logger.debug(
                "%s: actor '%s' has an inert record in case '%s' (joined=False)"
                " — not yet a participant",
                self.name,
                self.recommended_id,
                self.case_id,
            )
            return Status.FAILURE
        self.logger.info(
            "%s: actor '%s' is already a participant in case '%s'",
            self.name,
            self.recommended_id,
            self.case_id,
        )
        return Status.SUCCESS


class InviteInFlightNode(DataLayerActionWithPorts):
    """Return SUCCESS if an Invite to the recommended actor is in-flight.

    Finds the latest ``invite_actor_to_case`` entry inviting
    ``recommended_id`` (:func:`request_naming_actor_is_pending`) and returns
    SUCCESS when it is pending — i.e., an Invite was sent and no
    Accept/Reject has been recorded (AC-7a, CM-16-009).

    Used as the second arm of the duplicate-detection Selector in
    :func:`~vultron.core.behaviors.case.suggest_actor_tree.create_recommend_actor_to_case_received_tree`.
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
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if request_naming_actor_is_pending(
            self.datalayer,
            self.case_id,
            self.recommended_id,
            MessageSemantics.INVITE_ACTOR_TO_CASE.value,
            INVITE_ACTOR_TO_CASE_REPLY_TYPES,
            invitee,
        ):
            self.logger.info(
                "%s: Invite to '%s' is in-flight for case '%s'",
                self.name,
                self.recommended_id,
                self.case_id,
            )
            return Status.SUCCESS
        return Status.FAILURE


class PendingOfferCaseParticipantNode(DataLayerActionWithPorts):
    """Return SUCCESS if an Offer(CaseParticipant) to the Case Owner is pending.

    Finds the latest ``offer_case_participant`` entry whose participant
    record names ``recommended_id`` (:func:`request_naming_actor_is_pending`)
    and returns SUCCESS when it is pending — i.e., the CaseActor has already
    forwarded an Offer(CaseParticipant) for this actor and the Case Owner
    has not yet responded (AC-6, CM-16-008).

    Used as the third arm of the duplicate-detection Selector in
    :func:`~vultron.core.behaviors.case.suggest_actor_tree.create_recommend_actor_to_case_received_tree`.

    The Offer this recommendation (*recommendation_id*) forwards itself is
    not counted: its id derives from the recommendation, so a re-run from
    holding finds it, and must forward nothing new and write no duplicate
    note its first run never wrote (ADR-0154).
    """

    def __init__(
        self,
        recommended_id: str,
        case_id: str,
        recommendation_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.recommended_id = recommended_id
        self.case_id = case_id
        self.recommendation_id = recommendation_id

    def _own_offer_id(self) -> str:
        """The id of the Offer this recommendation forwards itself.

        Raises:
            VultronWiringError: the node runs with no executing actor.
        """
        if self.actor_id is None:
            raise VultronWiringError(
                f"{self.name}: no executing actor to derive the forwarded"
                " Offer(CaseParticipant) id from"
            )
        return offer_case_participant_id(
            self.actor_id, self.case_id, self.recommendation_id
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if request_naming_actor_is_pending(
            self.datalayer,
            self.case_id,
            self.recommended_id,
            MessageSemantics.OFFER_CASE_PARTICIPANT.value,
            OFFER_CASE_PARTICIPANT_REPLY_TYPES,
            offered_participant_actor,
            own_request_id=self._own_offer_id(),
        ):
            self.logger.info(
                "%s: Offer(CaseParticipant) for '%s' is pending Case Owner "
                "decision in case '%s'",
                self.name,
                self.recommended_id,
                self.case_id,
            )
            return Status.SUCCESS
        return Status.FAILURE


__all__ = [
    "ActorAlreadyParticipantNode",
    "InviteInFlightNode",
    "PendingOfferCaseParticipantNode",
]
