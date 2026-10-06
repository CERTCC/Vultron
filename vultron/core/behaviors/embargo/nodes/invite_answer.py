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

"""A participant answers the embargo Invite addressed to it (EP-09-003).

A participant that receives an ``Invite(EmbargoEvent)`` stores it and answers
it with ``Accept`` or ``Reject`` addressed to the CASE_MANAGER, through its
response decision (EMB-15).  It writes no EM or consent state: consent moves
when the CASE_MANAGER commits the answer and the replica replays that entry
(EP-09-007, ADR-0113).
"""

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.emit import _SendEmbargoActivityBase
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models._helpers import now_utc
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.services.embargo_duration import (
    actor_default_duration,
    stored_actor_profile,
)
from vultron.core.services.embargo_ordering import read_embargo_event
from vultron.core.states.em import EM
from vultron.errors import VultronNotFoundError, VultronWiringError


class CanAnswerEmbargoInviteNode(DataLayerConditionWithPorts):
    """SUCCESS when this store is the one that answers the Invite.

    Only the invitee answers — the Invite's sole ``to`` recipient, not whoever's
    store the Invite reached (EP-09-010) — and only once it holds the case, since
    the answer goes to the case's CASE_MANAGER (PCR-08-001), and the embargo the
    Invite proposes, since the answer carries the Invite whole.  An invitee
    missing either is a partial replica (Regime 2, ADR-0087): it keeps the
    Invite and answers nothing, and the WARNING says so.

    A copy addressed to neither ``to`` nor ``cc`` of this actor never gets
    here: ``unaddressed_copy_refusal()`` refuses it at the door, before any
    tree runs (HP-01-005, ADR-0118).  The not-the-invitee arm below is the
    backstop for a copy that *is* addressed to this actor (a ``cc``
    recipient) while it names someone else as the invitee.
    """

    def __init__(
        self,
        case_id: str,
        invitee_id: str,
        embargo_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._invitee_id = invitee_id
        self._embargo_id = embargo_id

    def update(self) -> Status:
        if self.actor_id != self._invitee_id:
            self.feedback_message = (
                f"'{self.actor_id}' is not the invitee '{self._invitee_id}'"
                " — the Invite is stored and not answered here"
            )
            # The door check already refused an unaddressed copy, so this is
            # a copy addressed to this actor (cc) naming another invitee: the
            # Invite is not this store's to answer (EP-09-010).
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if self.datalayer is None:
            # A FAILURE would read as "not answerable" through the Inverter
            # and drop the answer silently; a missing store is a wiring fault.
            raise VultronWiringError(
                f"{self.name}: no DataLayer to answer embargo Invite on case"
                f" '{self._case_id}'"
            )
        if self._resolve_case_replica(self._case_id) is None:
            self.feedback_message = (
                f"invitee '{self._invitee_id}' holds no copy of case"
                f" '{self._case_id}', so it cannot address an answer to the"
                " CASE_MANAGER — the Invite is stored and not answered"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if self.datalayer.read(self._embargo_id) is None:
            self.feedback_message = (
                f"invitee '{self._invitee_id}' does not hold embargo"
                f" '{self._embargo_id}', which the Invite names by id only —"
                " the Invite is stored and not answered"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


class OwnerMayAutoAcceptEmbargoNode(DataLayerConditionWithPorts):
    """SUCCESS when the case owner's prototype auto-accept may fire.

    The protocol never requires an automatic answer to an embargo Invite; the
    owner SHOULD gauge consensus first (EP-09-006).  This prototype bounds the
    one automatic answer it keeps: the owner accepts on its own only while no
    embargo exists (``EM.NONE``) and the proposal ends no later than the
    owner's own policy duration from now.  An owner that published no policy
    has nothing to bound the proposal against, so nothing is auto-accepted.
    Every other case — above all a revision Invite while an embargo is active
    or being revised — is left for the owner, or its policy call-out, to
    answer (EP-09-005).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id

    def update(self) -> Status:
        if self.datalayer is None:
            raise VultronWiringError(
                f"{self.name}: no DataLayer to bound the owner's auto-accept"
                f" on case '{self._case_id}'"
            )
        case = self._resolve_case_replica(self._case_id)
        if case is None or case.current_status.em_state != EM.NONE:
            self.feedback_message = (
                "an embargo exists or is being revised — the owner answers,"
                " nothing is auto-accepted (EP-09-006)"
            )
            return Status.FAILURE
        if self.actor_id is None:
            raise VultronWiringError(
                f"{self.name}: no actor_id to read the owner's embargo policy"
            )
        try:
            policy = actor_default_duration(
                stored_actor_profile(self.datalayer, self.actor_id)
            )
        except VultronNotFoundError:
            policy = None
        if policy is None:
            self.feedback_message = (
                "the owner published no embargo policy to bound the proposal"
                " — nothing is auto-accepted"
            )
            return Status.FAILURE
        proposal = read_embargo_event(self.datalayer, self._embargo_id)
        if proposal.end_time > now_utc() + policy:
            self.feedback_message = (
                f"proposal ends {proposal.end_time.isoformat()}, beyond the"
                f" owner's {policy} policy — nothing is auto-accepted"
            )
            return Status.FAILURE
        return Status.SUCCESS


class SendEmbargoInviteAnswerNode(_SendEmbargoActivityBase):
    """Queue an ``Accept`` or ``Reject`` of a stored embargo Invite.

    Addressed to the case's CASE_MANAGER (EP-09-003, PCR-08-001) and built by
    the trigger-activity port from the stored Invite.

    **Fails by raising, never by returning FAILURE.**  The node is the action
    of an arm in the EMB-15 response Selector, so a FAILURE from the accept
    arm would fall through to the reject arm and send the opposite answer.
    A missing factory, a case with no CASE_MANAGER (CM-24-006), a factory
    error or an outbox fault is a fault in this actor's own composition or
    store, never a decision, so it surfaces as one.  The base class's hooks
    each report FAILURE with a reason; ``update()`` is the one place that
    turns any non-SUCCESS into the raise.
    """

    def __init__(
        self,
        case_id: str,
        invite_id: str,
        *,
        accept: bool,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id=case_id, name=name)
        self._invite_id = invite_id
        self._accept = accept

    @property
    def _verb(self) -> str:
        return "Accept" if self._accept else "Reject"

    def _on_factory_unavailable(self) -> Status:
        self.feedback_message = (
            "trigger_activity_factory not available — cannot answer Invite"
            f" '{self._invite_id}' (BT-14-001)"
        )
        return Status.FAILURE

    def _resolve_embargo_and_manager(self) -> "tuple[str, str] | Status":
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure
        assert self.datalayer is not None
        manager_id = resolve_case_manager_id(case, self.datalayer)
        if manager_id is None:
            self.feedback_message = (
                f"case '{self._case_id}' has no CASE_MANAGER to answer"
                f" Invite '{self._invite_id}' to (CM-24-006)"
            )
            return Status.FAILURE
        return self._invite_id, manager_id

    def _call_factory(
        self, actor_id: str, invite_id: str, case_manager_id: str
    ) -> tuple[str, object]:
        assert self.trigger_activity_factory is not None
        build = (
            self.trigger_activity_factory.accept_embargo
            if self._accept
            else self.trigger_activity_factory.reject_embargo
        )
        return build(
            proposal_id=invite_id,
            case_id=self._case_id,
            actor=actor_id,
            to=[case_manager_id],
        )

    def _on_outbox_write_failure(
        self, activity_id: str, exc: Exception
    ) -> Status:
        self.feedback_message = (
            f"outbox write failed for {self._verb}(Invite) '{activity_id}':"
            f" {exc}"
        )
        return Status.FAILURE

    def update(self) -> Status:
        status = super().update()
        if status is not Status.SUCCESS:
            # A FAILURE here must not read as "try the other answer" (see
            # the class docstring), so every unsent answer raises.
            raise RuntimeError(
                f"{self.name}: {self.feedback_message or 'answer not sent'}"
            )
        return status


__all__ = [
    "CanAnswerEmbargoInviteNode",
    "OwnerMayAutoAcceptEmbargoNode",
    "SendEmbargoInviteAnswerNode",
]
