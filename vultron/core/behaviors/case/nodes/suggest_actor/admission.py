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

"""Admission guards for the suggest-actor workflow (CM-16).

The CASE_MANAGER runs these read-only checks in the received trees'
``precondition_guards``, so a refused recommendation, or a refused Case Owner
answer to one, commits no ledger entry and is answered by the refusal notice
alone (CLP-10-009, CLP-10-022).

Node classes:

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

The ``case_manager_*_guard`` factories compose them for the tree factories.
"""

from collections.abc import Iterable

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.suggest_actor.recorded_offer import (
    RecordedOfferAnswerInputMixin,
    RequireRecordedOfferAnswerNode,
)
from vultron.core.behaviors.case.stub_invite_lifetime import (
    awaiting_stub_reply,
    invitee_record,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_persistence import CasePersistence
from vultron.enums.roles import describe_authority_roles


def refusal_status(
    node: py_trees.behaviour.Behaviour, refusal: str | None
) -> Status:
    """``SUCCESS`` when *refusal* is ``None``; otherwise refuse with it.

    A refusal becomes *node*'s ``feedback_message``, which the factory puts
    in the refusal notice (CLP-05-005), and is logged at WARNING.
    """
    if refusal is None:
        return Status.SUCCESS
    node.feedback_message = refusal
    node.logger.warning("%s: %s", node.name, refusal)
    return Status.FAILURE


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
        return refusal_status(self, refusal)


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
        return refusal_status(
            self,
            f"actor '{invitee_id}' has already {state} in case"
            f" '{self.case_id}' and is sent no further stub Invite"
            " — REFUSED (CM-11-015, CM-16-006)",
        )


def authority_roles_refusal(
    subject: str, invitee_id: str, roles: Iterable[object]
) -> str | None:
    """The refusal for *subject* naming an authority role for *invitee_id*.

    ``None`` when *roles* names neither ``CASE_MANAGER`` nor ``CASE_OWNER``.
    An invitation adds a participant; it never confers either role, and the
    CASE_MANAGER refuses the request whole rather than strip the role, so
    nobody is invited with roles other than the ones asked for (CM-20-008).
    """
    named = describe_authority_roles(roles)
    if named is None:
        return None
    return f"{subject} for '{invitee_id}' names {named} — REFUSED (CM-20-008)"


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
        return refusal_status(self, refusal)


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


__all__ = [
    "AcceptedInviteeIsNotRemovedNode",
    "AcceptedRolesAreGrantableNode",
    "SuggestedActorIsInvitableNode",
    "SuggestedActorIsNotRemovedNode",
    "SuggestedRolesAreGrantableNode",
    "authority_roles_refusal",
    "case_manager_admits_accepted_invitee_guard",
    "case_manager_admits_suggested_actor_guard",
    "case_manager_requires_recorded_rejection_guard",
    "refusal_status",
    "removed_participant_refusal",
]
