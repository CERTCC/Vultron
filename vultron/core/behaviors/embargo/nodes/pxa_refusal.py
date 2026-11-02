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

"""The nodes of the P/X/A refusal of an embargo Invite or its Accept.

Once the case is public, an exploit is public or attacks are observed, a
received ``Invite(EmbargoEvent)`` (EMB-01-002) or ``Accept`` of one
(EMB-02-004) is refused and answered with a ``Reject`` of the Invite, the
receiver's own answer and not ER (MSM-02-010).
:func:`~vultron.core.behaviors.embargo.refusal_tree.pxa_invite_refusal` and
:func:`~vultron.core.behaviors.embargo.refusal_tree.pxa_accept_refusal`
compose these nodes into the diversion the two received trees carry.

The ``Reject`` is the receiver's record of its decision: its id derives from the
rejecting actor and the Invite, so a redelivery finds it already sent and is
skipped rather than answered twice (HP-01-003, CLP-13-001), and a ``Reject``
sealed but never queued is queued again (ID-04-005).
"""

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.invite_answer import (
    SendEmbargoInviteAnswerNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.predicates.embargo import pxa_is_embargo_eligible

__all__ = [
    "EmbargoInviteNotYetRefusedNode",
    "RefusalFactoryAvailableNode",
    "PxaBarsEmbargoNode",
    "ReceiverIsInviteeNode",
    "SendEmbargoProposalRefusalNode",
]


class PxaBarsEmbargoNode(DataLayerConditionWithPorts):
    """Condition: the case is public, an exploit is public or attacks are seen.

    SUCCESS when the receiver's copy of the case has any of P, X or A set, so
    no embargo may be proposed or accepted (EMB-01-002, EMB-02-004); its
    feedback message is the refusal's reason.  FAILURE otherwise, and when
    this store holds no such case, which bars nothing.  Read-only.
    """

    def __init__(
        self, case_id: str, reason: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self.reason = reason

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        case = self._resolve_case_replica(self._case_id)
        if case is None or pxa_is_embargo_eligible(
            case.current_status.pxa.state
        ):
            return Status.FAILURE
        self.feedback_message = self.reason
        self.logger.info("%s: %s", self.name, self.reason)
        return Status.SUCCESS


class ReceiverIsInviteeNode(DataLayerConditionWithPorts):
    """Guard: the executing actor is the Invite's invitee (EP-09-010).

    Only the invitee answers an Invite.  A store that holds a copy addressed
    otherwise (its own sent Invite, say) keeps it and answers nothing, and
    the WARNING says so.  Reads only the blackboard.
    """

    def __init__(
        self, invitee_id: str, invite_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id
        self._invite_id = invite_id

    def update(self) -> Status:
        if self.actor_id == self.invitee_id:
            return Status.SUCCESS
        self.feedback_message = (
            f"Invite '{self._invite_id}' is addressed to '{self.invitee_id}',"
            f" not to '{self.actor_id}' — no Reject sent (EP-09-010)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class RefusalFactoryAvailableNode(DataLayerActionWithPorts):
    """Guard: the trigger-activity port that builds the Reject is wired.

    Without it nothing can be built, so the refusal stands without its Reject and
    the WARNING says so; FAILURE.  Reads only its wiring.
    """

    def __init__(
        self, case_id: str, invite_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._invite_id = invite_id

    def update(self) -> Status:
        if self.trigger_activity_factory is not None:
            return Status.SUCCESS
        self.feedback_message = (
            f"trigger_activity unavailable — Reject not emitted by actor"
            f" '{self.actor_id}' for invite '{self._invite_id}' on case"
            f" '{self._case_id}'"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class EmbargoInviteNotYetRefusedNode(
    SilentIdempotencyGuardMixin, DataLayerActionWithPorts
):
    """Idempotency guard: this actor has not yet refused this Invite.

    FAILURE means the ``Reject`` was already sent; the handler reads it as a
    re-delivery (CLP-13-001, HP-01-003).  The ``Reject`` is sealed before
    it is queued, so one sealed but no longer pending is queued again under its
    own id rather than taken as delivered (ID-04-005).  A missing
    trigger-activity port sends nothing, so there is nothing to repeat.
    """

    def __init__(self, invite_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._invite_id = invite_id

    def update(self) -> Status:
        if self.trigger_activity_factory is None or self.actor_id is None:
            return Status.SUCCESS
        if self.trigger_activity_factory.requeue_embargo_refusal(
            self.actor_id, self._invite_id
        ):
            self.feedback_message = (
                f"Reject of Invite '{self._invite_id}' was already sent by"
                f" '{self.actor_id}'"
            )
            return self._idempotent_failure(
                self.logger,
                "%s: %s — skipping (CLP-13-001)",
                self.name,
                self.feedback_message,
            )
        return Status.SUCCESS


class SendEmbargoProposalRefusalNode(SendEmbargoInviteAnswerNode):
    """Queue the ``Reject`` of a refused ``Invite(EmbargoEvent)`` where it goes.

    The CASE_MANAGER answers the proposer that sent the Invite; any other
    actor answers the CASE_MANAGER, never a peer (EP-09-003, PCR-08-001).
    The recipient is resolved when the node runs, from the case's
    CASE_MANAGER, which is never unfilled (CM-24-006): a case naming none
    fails the node, and like every answer it then raises.
    """

    def __init__(
        self,
        case_id: str,
        invite_id: str,
        *,
        sender_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(
            case_id=case_id, invite_id=invite_id, accept=False, name=name
        )
        self._sender_id = sender_id

    def _resolve_embargo_and_manager(self) -> "tuple[str, str] | Status":
        resolved = super()._resolve_embargo_and_manager()
        if isinstance(resolved, Status):
            return resolved
        invite_id, manager_id = resolved
        if manager_id == self.actor_id:
            return invite_id, self._sender_id
        return invite_id, manager_id
