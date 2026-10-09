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
- :class:`SuggestedActorIsInvitableNode` — refuses the Case Owner's Accept of
  a recommendation for an actor that has joined or is at ``RM.CLOSED``
  (CM-11-015, CM-16-006).
- :class:`InviteInFlightNode` — returns SUCCESS when an Invite to the
  recommended actor is in-flight (CM-16-009 / AC-7a).
- :class:`PendingOfferCaseParticipantNode` — returns SUCCESS when an
  Offer(CaseParticipant) to the Case Owner is already pending (CM-16-008 /
  AC-6).
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.case.stub_invite_lifetime import (
    awaiting_stub_reply,
    invitee_record,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.protocol_pair import (
    INVITE_ACTOR_TO_CASE_REPLY_TYPES,
    OFFER_CASE_PARTICIPANT_REPLY_TYPES,
)


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


class SuggestedActorIsNotRemovedNode(DataLayerConditionWithPorts):
    """Guard: the actor a recommendation names is not a removed participant.

    A removed participant is sent no stub Invite (CM-31-013): the Case Owner
    took it out, and only the Case Owner's ``Add(CaseParticipant)`` brings it
    back (CM-31-011, ADR-0116).  So a recommendation of it, and the Case
    Owner's acceptance of one, are refused before the guarded commit, with a
    reason naming reinstatement.  An actor the case does not list, or one
    whose record carries no removal fact, passes.

    Read-only, so it runs in ``precondition_guards`` behind the CASE_MANAGER
    gate (CLP-10-009, RSH-08-003).
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
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: the CASE_MANAGER holds its case
        participant_id = case.actor_participant_index.get(self.recommended_id)
        record = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        if not (isinstance(record, CaseParticipant) and record.removed):
            return Status.SUCCESS
        self.feedback_message = (
            f"actor '{self.recommended_id}' is a removed participant of case"
            f" '{self.case_id}' and is sent no stub Invite; the Case Owner"
            " reinstates it with Add(CaseParticipant) — REFUSED (CM-31-013)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class SuggestedActorIsInvitableNode(DataLayerConditionWithPorts):
    """Guard: the actor the Case Owner accepted has not joined and is not closed.

    The Case Owner's ``Accept(Offer(CaseParticipant))`` makes the CASE_MANAGER
    send a stub Invite and commit it.  An actor whose record shows it has
    already joined, or is at ``RM.CLOSED``, is not invited again: the record
    is the actor's one record in the case, ``RM.CLOSED`` is terminal
    (CM-11-015, ADR-0085), and a joined actor has nothing left to answer.  So
    the Accept is refused before the guarded commit, with a reason, and
    nothing is written.  An actor with no record, or an inert one that has not
    answered (:func:`awaiting_stub_reply`), passes.

    Read-only, so it runs in ``precondition_guards`` behind the CASE_MANAGER
    gate (CLP-10-009, RSH-08-003).  The predicate is the one the re-invite
    arm uses; this guard adds no sender check (HP-01-006, ADR-0115).
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
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: the CASE_MANAGER holds its case
        record = invitee_record(self.datalayer, case, self.recommended_id)
        if record is None or awaiting_stub_reply(record):
            return Status.SUCCESS
        state = "joined" if record.joined else "at RM.CLOSED"
        self.feedback_message = (
            f"actor '{self.recommended_id}' has already {state} in case"
            f" '{self.case_id}' and is sent no further stub Invite"
            " — REFUSED (CM-11-015, CM-16-006)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


def case_manager_admits_accepted_invitee_guard(
    recommended_id: str, case_id: str
) -> py_trees.composites.Selector:
    """Precondition guard for the Case Owner's Accept of a recommendation.

    The CASE_MANAGER runs :class:`SuggestedActorIsNotRemovedNode` (CM-31-013)
    and then :class:`SuggestedActorIsInvitableNode`, so an Accept naming a
    removed, joined or closed actor is refused before the guarded commit; a
    replica skips both as ``SUCCESS`` (RSH-08-003).
    """
    return create_case_manager_gated_tree(
        name="AcceptedInviteeAdmittedIfCaseManager",
        case_id=case_id,
        body_name="AcceptedInviteeAdmitted",
        children=[
            SuggestedActorIsNotRemovedNode(
                recommended_id=recommended_id, case_id=case_id
            ),
            SuggestedActorIsInvitableNode(
                recommended_id=recommended_id, case_id=case_id
            ),
        ],
    )


def case_manager_admits_suggested_actor_guard(
    recommended_id: str, case_id: str
) -> py_trees.composites.Selector:
    """Precondition guard: when this actor is the CASE_MANAGER, the suggested actor is not removed.

    A read-only composite for the received tree's ``precondition_guards``
    (CLP-10-009), in the shape of ``case_manager_admits_removal_guard``: a
    replica skips it as ``SUCCESS`` (RSH-08-003), and the CASE_MANAGER runs
    :class:`SuggestedActorIsNotRemovedNode`, so a refused recommendation
    leaves no ledger entry (CM-31-013).
    """
    return create_case_manager_gated_tree(
        name="SuggestedActorNotRemovedIfCaseManager",
        case_id=case_id,
        body_name="SuggestedActorNotRemoved",
        children=[
            SuggestedActorIsNotRemovedNode(
                recommended_id=recommended_id, case_id=case_id
            )
        ],
    )


class InviteInFlightNode(DataLayerActionWithPorts):
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


class PendingOfferCaseParticipantNode(DataLayerActionWithPorts):
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
