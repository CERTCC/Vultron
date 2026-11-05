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

"""Read-only precondition guards of the embargo proposal relay (EP-09-001).

Split out of ``relay.py`` for the BTND-07-004 line limit, along the seam the
received tree already has: these run as ``precondition_guards``, ahead of the
guarded commit, and write nothing; ``relay.py`` holds the recipient
collection and the relay emit, and re-exports these names.
"""

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.path_branch import OnPaths
from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.embargo.nodes.proposal_repeat import (
    EmbargoTermsNotHeldNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.states.em import is_em_exited
from vultron.errors import BtNodePreconditionError


class EmbargoProposalNotYetRecordedNode(
    SilentIdempotencyGuardMixin, DataLayerConditionWithPorts
):
    """Idempotency guard: this exact Invite is not the one the index holds.

    The latch is ``case.pending_embargo_proposal_index[embargo_id] ==
    invite_id``, which the handler writes only after the whole tree succeeded
    (ID-04-005).  A re-delivered proposal — an outbox retry, a replayed
    inbox — would otherwise re-run the counter-proposal branch and relay a
    second round of Invites.  A precondition guard, so the duplicate commits
    no ledger entry (CLP-13-001); the handler reads its FAILURE as SKIPPED
    (HP-01-003).  A case this store does not hold cannot have recorded
    anything, so that is SUCCESS, not a refusal.

    The index holds only undecided proposals (EP-08-003), so it catches a
    repeat only while the proposal is open: once the proposal is decided, or
    when the Invite arrived after its decision, nothing is indexed.  The
    participant's answer is then latched by
    :class:`EmbargoInviteNotYetAnsweredNode` instead.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        invite_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._invite_id = invite_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case = self._resolve_case_replica(self._case_id)
        if case is None:
            return Status.SUCCESS
        recorded = case.pending_embargo_proposal_index.get(self._embargo_id)
        if recorded == self._invite_id:
            self.feedback_message = (
                f"Invite '{self._invite_id}' for embargo '{self._embargo_id}'"
                f" was already applied on case '{self._case_id}'"
            )
            return self._idempotent_failure(
                self.logger,
                "%s: %s — skipping (CLP-13-001)",
                self.name,
                self.feedback_message,
            )
        return Status.SUCCESS


class EmbargoInviteNotYetAnsweredNode(
    SilentIdempotencyGuardMixin, DataLayerActionWithPorts
):
    """Idempotency guard: the invitee has not already answered this Invite.

    The replica's answer to an ``Invite(EmbargoEvent)`` addressed to it is
    one activity per Invite, under an id derived from the invitee and the
    Invite (ID-04-004), so the trigger-activity port can say whether it was
    sent (``answered_embargo_invite``).  A re-delivered Invite it already
    answered fails here, so it queues no second answer and the handler reads
    it as SKIPPED (CLP-13-001, HP-01-014).  This holds in either arrival
    order: whether the Invite came before its proposal's decision, whose
    register step then took it out of the proposal index, or after it, when
    it was never indexed (EP-08-003, SYNC-19-001).

    The answer is sealed and queued in the same act as the rest of the tree
    (ADR-0146), so a sealed answer is a queued one (ID-04-005).  Reads only:
    a store other than the invitee's, or one with no trigger-activity port,
    has sent nothing, so that is SUCCESS.  Declared on the participant path
    alone; the CASE_MANAGER's own repeat is :class:`EmbargoProposalNotYetRecordedNode`.
    """

    def __init__(
        self,
        invitee_id: str,
        invite_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._invitee_id = invitee_id
        self._invite_id = invite_id

    def update(self) -> Status:
        factory = self.trigger_activity_factory
        actor_id = self.actor_id
        if factory is None or actor_id is None or actor_id != self._invitee_id:
            return Status.SUCCESS
        if factory.answered_embargo_invite(actor_id, self._invite_id):
            self.feedback_message = (
                f"Invite '{self._invite_id}' was already answered by"
                f" '{actor_id}'"
            )
            return self._idempotent_failure(
                self.logger,
                "%s: %s — skipping (CLP-13-001)",
                self.name,
                self.feedback_message,
            )
        return Status.SUCCESS


class EmStateAdmitsProposalNode(DataLayerConditionWithPorts):
    """Guard: the case's EM state accepts a PROPOSE trigger.

    A read-only precondition guard (CLP-10-009) for the CASE_MANAGER's
    adjudication of a received proposal: ``NONE``, ``PROPOSED``, ``ACTIVE``
    and ``REVISE`` admit one (EP-09-001), ``EXITED`` does not — the EM
    machine never returns from ``EXITED``.  Placed ahead of the guarded
    commit so a refused proposal leaves no canonical entry behind.  Reads the
    state through :class:`ReadEmStateNode` (AC-1, #1474).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        try:
            em_before = read_case_em_state(self.datalayer, self._case_id)
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE

        if is_em_exited(em_before):
            # The register accepts no change once its embargo has ended
            # (ADR-0122).
            self.feedback_message = (
                f"Case '{self._case_id}' is at EM {em_before.name}, which"
                " admits no embargo proposal (EP-09-001)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


def invitee_not_yet_answered_guard(invitee_id: str, invite_id: str) -> OnPaths:
    """Precondition guard: off the manager path, the invitee has not answered yet.

    A read-only declaration for the Invite tree's ``precondition_guards``
    (CLP-10-009): it runs :class:`EmbargoInviteNotYetAnsweredNode` on every
    path but the CASE_MANAGER's, whose repeat
    :class:`EmbargoProposalNotYetRecordedNode` and the EP-09-032 terms guard
    catch.  The factory builds the branch from the path stage's answer
    (HP-01-037, HP-01-038).

    Args:
        invitee_id: The Invite's sole ``to`` recipient, the one that answers.
        invite_id: The received Invite.
    """
    return OnPaths.off_case_manager(
        "InviteNotYetAnsweredOnReplica",
        EmbargoInviteNotYetAnsweredNode(
            invitee_id=invitee_id, invite_id=invite_id
        ),
    )


def case_manager_admits_proposal_guard(
    case_id: str,
    embargo_id: str,
    embargo: EmbargoEvent | None = None,
) -> OnPaths:
    """Precondition guard: on the manager path, the canonical case takes the proposal.

    A read-only declaration for a received tree's ``precondition_guards``
    (CLP-10-009), on the CASE_MANAGER path the Invite tree declares
    (HP-01-038): the factory builds the branch from the path stage's answer.
    It runs :class:`EmStateAdmitsProposalNode`, then
    :class:`~vultron.core.behaviors.embargo.nodes.proposal_repeat.EmbargoTermsNotHeldNode`,
    so a proposal the canonical case cannot take is refused, and one of terms
    the case already holds is a repeat (EP-09-032), before the guarded commit
    writes an entry for it.  The invitee's replica — which asks nothing of
    the canonical EM state or register (EP-09-003) — skips both.  No second
    role read: the branch reads the one answer the path stage already gave
    (HP-01-037).

    Args:
        case_id: The case the proposal is for.
        embargo_id: The proposed ``EmbargoEvent``.
        embargo: Its inline terms, when the message carries them; else they
            are read from the store.
    """
    return OnPaths.at_case_manager(
        "AdmitsEmbargoProposalOnManagerPath",
        EmStateAdmitsProposalNode(case_id=case_id),
        EmbargoTermsNotHeldNode(
            case_id=case_id, embargo_id=embargo_id, embargo=embargo
        ),
    )


__all__ = [
    "EmStateAdmitsProposalNode",
    "EmbargoInviteNotYetAnsweredNode",
    "EmbargoProposalNotYetRecordedNode",
    "case_manager_admits_proposal_guard",
    "invitee_not_yet_answered_guard",
]
