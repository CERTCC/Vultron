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
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.protocol_pair import (
    INVITE_ACTOR_TO_CASE_REPLY_TYPES,
    OFFER_CASE_PARTICIPANT_REPLY_TYPES,
)


class ActorAlreadyParticipantNode(DataLayerAction):
    """Return SUCCESS if the recommended actor is already a case participant.

    Reads ``VulnerabilityCase.actor_participant_index`` from the DataLayer.
    Returns SUCCESS when ``recommended_id`` is a key in the index (AC-7b,
    CM-16-009).

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


__all__ = [
    "ActorAlreadyParticipantNode",
    "InviteInFlightNode",
    "PendingOfferCaseParticipantNode",
]
