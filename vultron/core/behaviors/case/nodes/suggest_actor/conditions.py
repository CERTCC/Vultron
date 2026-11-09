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
- :class:`SuggestedActorIsNotRemovedNode` and
  :class:`AcceptedInviteeIsNotRemovedNode` — refuse a recommendation, or the
  Case Owner's Accept of one, naming a removed participant (CM-31-013).
- :class:`SuggestedActorIsInvitableNode` — refuses the Case Owner's Accept of
  a recommendation for an actor that has joined or is at ``RM.CLOSED``
  (CM-11-015, CM-16-006).
- :class:`SuggestedRolesAreGrantableNode` and
  :class:`AcceptedRolesAreGrantableNode` — refuse a recommendation, or the
  Case Owner's Accept of one, that names ``CASE_MANAGER`` or ``CASE_OWNER``
  for the invitee (CM-20-008).
- :class:`InviteInFlightNode` — returns SUCCESS when an Invite to the
  recommended actor is in-flight (CM-16-009 / AC-7a).
- :class:`PendingOfferCaseParticipantNode` — returns SUCCESS when an
  Offer(CaseParticipant) to the Case Owner is already pending (CM-16-008 /
  AC-6).
"""

from collections.abc import Iterable

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.suggest_actor.emit import (
    offer_case_participant_id,
)
from vultron.core.behaviors.case.nodes.suggest_actor.pending_request import (
    invitee,
    offered_participant_actor,
    request_naming_actor_is_pending,
)
from vultron.core.behaviors.case.nodes.suggest_actor.recorded_offer import (
    RecordedOfferAnswerInputMixin,
    RequireRecordedOfferAnswerNode,
)
from vultron.core.behaviors.case.stub_invite_lifetime import (
    awaiting_stub_reply,
    invitee_record,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.protocol_pair import (
    INVITE_ACTOR_TO_CASE_REPLY_TYPES,
    OFFER_CASE_PARTICIPANT_REPLY_TYPES,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.enums.roles import authority_roles_named
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


def removed_participant_refusal(
    datalayer: CasePersistence,
    case: VulnerabilityCase,
    actor_id: str,
    case_id: str,
) -> str | None:
    """The refusal for suggesting *actor_id* when it is a removed participant.

    ``None`` when the case does not list the actor, or its record carries no
    removal fact (CM-31-013).
    """
    participant_id = case.actor_participant_index.get(actor_id)
    record = datalayer.read(participant_id) if participant_id else None
    if not (isinstance(record, CaseParticipant) and record.removed):
        return None
    return (
        f"actor '{actor_id}' is a removed participant of case"
        f" '{case_id}' and is sent no stub Invite; the Case Owner"
        " reinstates it with Add(CaseParticipant) — REFUSED (CM-31-013)"
    )


class _NotRemovedGuardBase(DataLayerConditionWithPorts):
    """Refuse when the actor :meth:`_suggested_actor` names was removed.

    A removed participant is sent no stub Invite (CM-31-013): the Case Owner
    took it out, and only the Case Owner's ``Add(CaseParticipant)`` brings it
    back (CM-31-011, ADR-0116).  So a recommendation of it, and the Case
    Owner's acceptance of one, are refused before the guarded commit, with a
    reason naming reinstatement.  An actor the case does not list, or one
    whose record carries no removal fact, passes.

    Read-only, so it runs in ``precondition_guards`` behind the CASE_MANAGER
    gate (CLP-10-009, RSH-08-003).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def _suggested_actor(self) -> str:
        """The actor whose removal the guard checks."""
        raise NotImplementedError

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: the CASE_MANAGER holds its case
        refusal = removed_participant_refusal(
            self.datalayer, case, self._suggested_actor(), self.case_id
        )
        if refusal is None:
            return Status.SUCCESS
        self.feedback_message = refusal
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class SuggestedActorIsNotRemovedNode(_NotRemovedGuardBase):
    """Guard: the actor a recommendation names is not a removed participant.

    The recommended actor is fixed at construction; see
    :class:`_NotRemovedGuardBase` for the rule.
    """

    def __init__(
        self,
        recommended_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id=case_id, name=name)
        self.recommended_id = recommended_id

    def _suggested_actor(self) -> str:
        return self.recommended_id


class AcceptedInviteeIsNotRemovedNode(
    RecordedOfferAnswerInputMixin, _NotRemovedGuardBase
):
    """Guard: the invitee of the Offer the Case Owner accepted was not removed.

    The invitee is the recorded Offer's, read from the answer that
    ``RequireRecordedOfferAnswerNode`` published for *answer_id*
    (CM-16-019); see :class:`_NotRemovedGuardBase` for the rule.
    """

    def __init__(
        self, answer_id: str, case_id: str, name: str | None = None
    ) -> None:
        super().__init__(case_id=case_id, name=name)
        self._read_answer_of(answer_id)

    def _suggested_actor(self) -> str:
        return self._recorded_answer().invitee_id


class SuggestedActorIsInvitableNode(
    RecordedOfferAnswerInputMixin, DataLayerConditionWithPorts
):
    """Guard: the actor the Case Owner accepted has not joined and is not closed.

    The Case Owner's ``Accept(Offer(CaseParticipant))`` makes the CASE_MANAGER
    send a stub Invite and commit it.  An actor whose record shows it has
    already joined, or is at ``RM.CLOSED``, is not invited again: the record
    is the actor's one record in the case, ``RM.CLOSED`` is terminal
    (CM-11-043, ADR-0085), and a joined actor has nothing left to answer.  So
    the Accept is refused before the guarded commit, with a reason, and
    nothing is written.  An actor with no record, or an inert one that has not
    answered (:func:`awaiting_stub_reply`), passes.

    The actor is the recorded Offer's invitee, read from the answer that
    ``RequireRecordedOfferAnswerNode`` published for *answer_id*
    (CM-16-019).

    Read-only, so it runs in ``precondition_guards`` behind the CASE_MANAGER
    gate (CLP-10-009, RSH-08-003).  The predicate is the one the re-invite
    arm uses; this guard adds no sender check (HP-01-006, ADR-0115).
    """

    def __init__(
        self,
        answer_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._read_answer_of(answer_id)

    def update(self) -> Status:
        # This node replaces the mixin's update(), so it reads the published
        # answer first itself: a tree built without the lookup guard is a
        # wiring error, never a refusal, even when the case is missing.
        invitee_id = self._recorded_answer().invitee_id
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: the CASE_MANAGER holds its case
        record = invitee_record(self.datalayer, case, invitee_id)
        if record is None or awaiting_stub_reply(record):
            return Status.SUCCESS
        state = "joined" if record.joined else "at RM.CLOSED"
        self.feedback_message = (
            f"actor '{invitee_id}' has already {state} in case"
            f" '{self.case_id}' and is sent no further stub Invite"
            " — REFUSED (CM-11-015, CM-16-006)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


def authority_roles_refusal(
    subject: str, invitee_id: str, roles: Iterable[object]
) -> str | None:
    """The refusal for *subject* naming an authority role for *invitee_id*.

    ``None`` when *roles* names neither ``CASE_MANAGER`` nor ``CASE_OWNER``.
    An invitation adds a participant; it never confers either role, and the
    CASE_MANAGER refuses the request whole rather than strip the role, so
    nobody is invited with roles other than the ones asked for (CM-20-008).
    """
    named = authority_roles_named(roles)
    if not named:
        return None
    listed = ", ".join(role.value for role in named)
    return (
        f"{subject} names {listed} for '{invitee_id}', which no invitation"
        " confers; ownership moves by transfer and the CASE_MANAGER role by"
        " delegation — REFUSED (CM-20-008)"
    )


class _RolesAreGrantableGuardBase(DataLayerConditionWithPorts):
    """Refuse when the roles :meth:`_invitation` names hold an authority role.

    Read-only and before the guarded commit, so a refused request leaves no
    ledger entry and is answered only by the refusal notice (CLP-10-009,
    CLP-05-005).
    """

    def _invitation(self) -> tuple[str, str, Iterable[object]]:
        """``(subject, invitee_id, roles)`` of the request the guard judges."""
        raise NotImplementedError

    def update(self) -> Status:
        refusal = authority_roles_refusal(*self._invitation())
        if refusal is None:
            return Status.SUCCESS
        self.feedback_message = refusal
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class SuggestedRolesAreGrantableNode(_RolesAreGrantableGuardBase):
    """Guard: a recommendation suggests no authority role for the invitee.

    The roles are the received ``Offer(Actor)``'s ``suggestedRoles``, fixed
    at construction.  The guard runs on every path the recommend tree takes:
    a Coordinator's suggestion and the Case Owner's own invitation alike
    (CM-20-006, CM-20-008).
    """

    def __init__(
        self,
        recommendation_id: str,
        recommended_id: str,
        suggested_roles: list[str] | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.recommendation_id = recommendation_id
        self.recommended_id = recommended_id
        self.suggested_roles = list(suggested_roles or [])

    def _invitation(self) -> tuple[str, str, Iterable[object]]:
        return (
            f"Offer(Actor) '{self.recommendation_id}'",
            self.recommended_id,
            self.suggested_roles,
        )


class AcceptedRolesAreGrantableNode(
    RecordedOfferAnswerInputMixin, _RolesAreGrantableGuardBase
):
    """Guard: the Offer the Case Owner accepted names no authority role.

    The roles are the recorded Offer's, read from the answer that
    ``RequireRecordedOfferAnswerNode`` published for *answer_id*
    (CM-16-018).  The recommend tree refuses such a suggestion before it is
    forwarded, so this guard catches an Offer recorded by other means, such
    as one stored before that check (CM-20-006, CM-20-008).
    """

    def __init__(
        self, answer_id: str, case_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._read_answer_of(answer_id)

    def _invitation(self) -> tuple[str, str, Iterable[object]]:
        answer = self._recorded_answer()
        return (
            "the accepted Offer(CaseParticipant)",
            answer.invitee_id,
            answer.roles,
        )


def case_manager_admits_accepted_invitee_guard(
    answer_id: str, case_id: str
) -> py_trees.composites.Sequence:
    """Precondition guard for the Case Owner's Accept of a recommendation.

    The CASE_MANAGER looks up the Offer the Accept names and the
    recommendation behind it (:class:`RequireRecordedOfferAnswerNode`), then
    runs :class:`AcceptedInviteeIsNotRemovedNode` (CM-31-013) and
    :class:`SuggestedActorIsInvitableNode` on the recorded invitee and
    :class:`AcceptedRolesAreGrantableNode` on its recorded roles.  So an
    Accept naming an Offer it never recorded, a removed, joined or closed
    actor, or an authority role (CM-20-008) is refused before the guarded
    commit.

    The four run bare, with no gate of their own: their tree declares the
    CASE_MANAGER path alone, so the path door stage has already refused every
    other receiver and a gate here would ask the role a second time
    (HP-01-036, HP-01-038).  The composite keeps the gate body's name, so a
    built tree still reads the same.
    """
    return py_trees.composites.Sequence(
        name="AcceptedInviteeAdmitted",
        memory=False,
        children=[
            RequireRecordedOfferAnswerNode(
                verb="Accept", answer_id=answer_id, case_id=case_id
            ),
            AcceptedInviteeIsNotRemovedNode(
                answer_id=answer_id, case_id=case_id
            ),
            SuggestedActorIsInvitableNode(
                answer_id=answer_id, case_id=case_id
            ),
            AcceptedRolesAreGrantableNode(
                answer_id=answer_id, case_id=case_id
            ),
        ],
    )


def case_manager_requires_recorded_rejection_guard(
    answer_id: str, case_id: str
) -> py_trees.behaviour.Behaviour:
    """Precondition guard for the Case Owner's Reject of a recommendation.

    The CASE_MANAGER looks up the Offer the Reject names and the
    recommendation behind it (:class:`RequireRecordedOfferAnswerNode`), so a
    Reject naming either unrecorded is refused before the guarded commit.
    One node, run bare for the reason in
    :func:`case_manager_admits_accepted_invitee_guard`.
    """
    return RequireRecordedOfferAnswerNode(
        verb="Reject",
        answer_id=answer_id,
        case_id=case_id,
        name="RejectedOfferRecorded",
    )


def case_manager_admits_suggested_actor_guard(
    recommendation_id: str,
    recommended_id: str,
    case_id: str,
    suggested_roles: list[str] | None,
) -> py_trees.composites.Sequence:
    """Precondition guard: the recommendation may be admitted.

    A read-only guard for the received tree's ``precondition_guards``
    (CLP-10-009): :class:`SuggestedActorIsNotRemovedNode` (CM-31-013), then
    :class:`SuggestedRolesAreGrantableNode` (CM-20-008), so a refused
    recommendation leaves no ledger entry.  The two run bare for the reason
    in :func:`case_manager_admits_accepted_invitee_guard`.
    """
    return py_trees.composites.Sequence(
        name="SuggestedActorAdmissible",
        memory=False,
        children=[
            SuggestedActorIsNotRemovedNode(
                recommended_id=recommended_id,
                case_id=case_id,
                name="SuggestedActorNotRemoved",
            ),
            SuggestedRolesAreGrantableNode(
                recommendation_id=recommendation_id,
                recommended_id=recommended_id,
                suggested_roles=suggested_roles,
                name="SuggestedRolesGrantable",
            ),
        ],
    )


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
    "AcceptedInviteeIsNotRemovedNode",
    "AcceptedRolesAreGrantableNode",
    "SuggestedActorIsInvitableNode",
    "SuggestedActorIsNotRemovedNode",
    "SuggestedRolesAreGrantableNode",
    "authority_roles_refusal",
    "case_manager_admits_accepted_invitee_guard",
    "case_manager_admits_suggested_actor_guard",
    "case_manager_requires_recorded_rejection_guard",
    "removed_participant_refusal",
]
