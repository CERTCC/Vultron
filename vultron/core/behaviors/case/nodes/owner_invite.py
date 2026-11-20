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

"""Nodes for the Case Owner's own case Invite (CM-17-007, ADR-0199).

The Case Owner decides whom to invite, and says so with its own
``Invite(<case preview>)[target=<invitee>]``, sent to the CASE_MANAGER.  The
CASE_MANAGER runs the read-only guards here in the received tree's
``precondition_guards``, so a refused Invite commits no ledger entry, sends no
stub Invite and is answered by the refusal notice alone (CLP-10-009,
CLP-10-022):

- :class:`InviterHoldsCaseOwnerNode` — the sender holds ``CASE_OWNER``.
- :class:`InviteeIsNotCaseAuthorityNode` — the ``target`` is neither the
  CASE_MANAGER nor the Owner (CM-17-015).
- :class:`InviteeIsNotRemovedNode` — the invitee was not removed (CM-31-013).
- :class:`InviteeIsInvitableNode` — the invitee has not joined and is not at
  ``RM.CLOSED`` (CM-11-015, CM-11-043).
- :class:`OwnerInviteRolesAreGrantableNode` — the Invite offers at least one
  role, and neither authority role (CM-11-048, CM-20-008).

:class:`RecommenderIsNotCaseOwnerNode` is the other half of the one wire
form: the recommend-actor tree refuses the Owner's ``Offer(Actor)``, because
the Owner's decision travels as its Invite.

The stub Invite the CASE_MANAGER then sends is built in
:mod:`~vultron.core.behaviors.case.nodes.owner_invite_stub`
(:func:`owner_decided_stub_invite`), whose names this module re-exports.

Every node reads the case, the invitee and the sender from the per-act keys
``/case_id``, ``/invitee_id`` and ``/sender_id`` (BTND-01-008, BTND-01-009);
a factory that holds the values seeds them with
:func:`~vultron.core.behaviors.act_key_scope.with_act_keys`.
"""

from collections.abc import Iterable

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.owner_invite_stub import (
    EmitOwnerDecidedStubInviteNode,
    InviteeAwaitsReplyNode,
    SeatOwnerInvitedInviteeNode,
    _InviteKeysMixin,
    owner_decided_stub_invite,
)
from vultron.core.behaviors.case.nodes.suggest_actor.admission import (
    _RolesAreGrantableGuardBase,
    not_invitable_refusal,
    refusal_status,
    removed_participant_refusal,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.participants.role_predicate import has_role
from vultron.enums.roles import CVDRole
from vultron.primitives import same_actor_id


class _CaseOwnerStandingGuardBase(
    _InviteKeysMixin, DataLayerConditionWithPorts
):
    """Refuse unless the sender's ``CASE_OWNER`` standing is what the act needs.

    The standing is read from the CASE_MANAGER's roster through
    :func:`~vultron.core.participants.role_predicate.has_role`, the one
    source of a role answer (ARCH-24-008).  Subclasses state which answer
    passes (:attr:`_passes_when_owner`) and the refusal for the other.
    """

    _passes_when_owner: bool

    def _refusal(self, sender_id: str, case_id: str) -> str:
        """The refusal reason when the standing is the wrong one."""
        raise NotImplementedError

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        sender_id, case_id = self._act_sender(), self._act_case()
        is_owner = has_role(
            sender_id, case_id, CVDRole.CASE_OWNER, self.datalayer
        )
        if is_owner is self._passes_when_owner:
            return Status.SUCCESS
        return refusal_status(self, self._refusal(sender_id, case_id))


class InviterHoldsCaseOwnerNode(_CaseOwnerStandingGuardBase):
    """Guard: the sender of a case Invite to the CASE_MANAGER is the Case Owner.

    The Case Owner alone decides whom the case invites (CM-17-007), so an
    Invite from any other participant is refused with a reason.
    """

    _passes_when_owner = True

    def _refusal(self, sender_id: str, case_id: str) -> str:
        return (
            f"'{sender_id}' does not hold CASE_OWNER in case '{case_id}':"
            " only the Case Owner invites an actor with its own Invite; a"
            " participant suggests one with"
            " Offer(Actor)[target=VulnerabilityCase] — REFUSED (CM-17-007,"
            " CM-16-001, ADR-0199)"
        )


class RecommenderIsNotCaseOwnerNode(_CaseOwnerStandingGuardBase):
    """Guard: the sender of an actor recommendation is not the Case Owner.

    The Owner decides whom to invite and sends that decision as its own
    ``Invite(<case preview>)[target=<invitee>]`` (CM-17-007).  An
    ``Offer(Actor)[target=VulnerabilityCase]`` from it is refused, so the
    Owner's decision has one wire form (CM-17-027, ADR-0199).
    """

    _passes_when_owner = False

    def _refusal(self, sender_id: str, case_id: str) -> str:
        return (
            f"'{sender_id}' holds CASE_OWNER in case '{case_id}': the Case"
            " Owner invites an actor with its own"
            " Invite(<case preview>)[target=<invitee>], not an Offer(Actor)"
            " — REFUSED (CM-17-007, CM-17-027, ADR-0199)"
        )


class InviteeIsNotCaseAuthorityNode(
    _InviteKeysMixin, DataLayerConditionWithPorts
):
    """Guard: the Invite's ``target`` is neither the CASE_MANAGER nor the inviter.

    The CASE_MANAGER never addresses a stub Invite to itself (CM-17-015), and
    the Case Owner is already on the case it owns.  The CASE_MANAGER is the
    receiving actor: the guard runs on the manager path alone.
    """

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.actor_id is not None
        invitee_id = self._act_invitee()
        if same_actor_id(invitee_id, self.actor_id):
            who = "the CASE_MANAGER"
        elif same_actor_id(invitee_id, self._act_sender()):
            who = "the Case Owner that sent it"
        else:
            return Status.SUCCESS
        return refusal_status(
            self,
            f"the Invite's target '{invitee_id}' is {who} of case"
            f" '{self._act_case()}', which is sent no stub Invite — REFUSED"
            " (CM-17-015, CM-17-026)",
        )


class InviteeIsNotRemovedNode(_InviteKeysMixin, DataLayerConditionWithPorts):
    """Guard: the invitee is not a removed participant (CM-31-013).

    A removed participant is sent no stub Invite; only the Case Owner's
    ``Add(CaseParticipant)`` reinstates it (CM-31-011).  The predicate is
    :func:`~vultron.core.behaviors.case.nodes.suggest_actor.admission.removed_participant_refusal`,
    the one a suggestion is judged by.
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case_id = self._act_case()
        case, failure = self._require_case(case_id)
        if failure is not None:
            return failure  # Regime 1: the CASE_MANAGER holds its case
        refusal = removed_participant_refusal(
            self.datalayer, case, self._act_invitee(), case_id
        )
        return refusal_status(self, refusal)


class InviteeIsInvitableNode(_InviteKeysMixin, DataLayerConditionWithPorts):
    """Guard: the invitee has not joined the case and is not at ``RM.CLOSED``.

    An actor with no record is invited; an inert one that has not answered is
    re-invited on its record (CM-11-015).  The predicate is
    :func:`~vultron.core.behaviors.case.nodes.suggest_actor.admission.not_invitable_refusal`,
    the one the Case Owner's Accept of a suggestion is judged by.
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self._act_case())
        if failure is not None:
            return failure  # Regime 1: the CASE_MANAGER holds its case
        refusal = not_invitable_refusal(
            self.datalayer, case, self._act_invitee()
        )
        return refusal_status(self, refusal)


class OwnerInviteRolesAreGrantableNode(
    _InviteKeysMixin, _RolesAreGrantableGuardBase
):
    """Guard: the Owner's Invite offers at least one role, and no authority role.

    The Owner names the invitee's roles and the CASE_MANAGER guesses none
    (CM-11-019, CM-11-050): an Invite with no role is refused rather than
    defaulted, and one naming ``CASE_MANAGER`` or ``CASE_OWNER`` is refused
    whole rather than stripped (CM-20-008).
    """

    def __init__(
        self, roles: list[str] | None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.roles = list(roles or [])

    def _invitation(self) -> tuple[str, str, Iterable[object]]:
        return ("The Case Owner's Invite", self._act_invitee(), self.roles)

    def update(self) -> Status:
        if not self.roles:
            return refusal_status(
                self,
                f"The Case Owner's Invite of '{self._act_invitee()}' offers"
                " no role; the CASE_MANAGER assigns none in its place —"
                " REFUSED (CM-11-019, CM-11-048, CM-11-050)",
            )
        return super().update()


def case_manager_admits_owner_invite_guard(
    roles: list[str] | None,
) -> py_trees.composites.Sequence:
    """Precondition guard: the Case Owner's Invite may be admitted.

    Runs :class:`InviterHoldsCaseOwnerNode`,
    :class:`InviteeIsNotCaseAuthorityNode`, :class:`InviteeIsNotRemovedNode`,
    :class:`InviteeIsInvitableNode` and
    :class:`OwnerInviteRolesAreGrantableNode`, in that order, so a refused
    Invite leaves no ledger entry and its refusal notice names the first
    failed check.  Every node is read-only (CLP-10-009).
    """
    return py_trees.composites.Sequence(
        name="OwnerInviteAdmissible",
        memory=False,
        children=[
            InviterHoldsCaseOwnerNode(name="InviterIsCaseOwner"),
            InviteeIsNotCaseAuthorityNode(name="InviteeIsNotCaseAuthority"),
            InviteeIsNotRemovedNode(name="InviteeNotRemoved"),
            InviteeIsInvitableNode(name="InviteeIsInvitable"),
            OwnerInviteRolesAreGrantableNode(
                roles=roles, name="OwnerInviteRolesGrantable"
            ),
        ],
    )


__all__ = [
    "EmitOwnerDecidedStubInviteNode",
    "InviteeAwaitsReplyNode",
    "InviteeIsInvitableNode",
    "InviteeIsNotCaseAuthorityNode",
    "InviteeIsNotRemovedNode",
    "InviterHoldsCaseOwnerNode",
    "OwnerInviteRolesAreGrantableNode",
    "RecommenderIsNotCaseOwnerNode",
    "SeatOwnerInvitedInviteeNode",
    "case_manager_admits_owner_invite_guard",
    "owner_decided_stub_invite",
]
