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

"""Nodes for a signatory's withdrawal from the embargo in force (MSM-07-010).

Withdrawal is ``Leave(EmbargoEvent)[context=VulnerabilityCase]``
(ADR-0122): a participant whose consent row for the embargo in force is
``AGREED`` ends its own consent, and the embargo stays in force for
everyone else (VP-13-017).  It is not an answer to an Invite, so a
``Reject(Invite(EmbargoEvent))`` never withdraws (MSM-07-004).

- :class:`IsWithdrawableEmbargoNode` — the received tree's read-only guard
  ahead of the commit (CLP-10-009).
- :class:`RejectIsNotWithdrawalNode` — the Reject tree's read-only guard that
  refuses a Reject reading as a withdrawal.
- :class:`RecordParticipantWithdrawalNode` — the CASE_MANAGER's effect.
- :class:`WithdrawEmbargoLifecycleNode` — the trigger's CASE_MANAGER arm.
- :class:`ApplyEmbargoWithdrawalFromLedgerNode` — the replica replay
  (EP-09-007, RSH-08-004).

Each check calls the shared predicates in
:mod:`vultron.core.services.embargo_lifecycle.pec`, which the lifecycle's own
refusal also calls, so the guard and the write cannot drift.
"""

from collections.abc import Callable
from typing import ClassVar

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.lifecycle import (
    _EmbargoLifecycleNode,
)
from vultron.core.behaviors.embargo.nodes.relay_effect import (
    _EmbargoRelayEffectNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.nodes._helpers import _extract_id_from_field
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    EmbargoLifecycleResult,
    embargo_withdrawal_refusal,
    participant_consent_row,
    reject_is_withdrawal_refusal,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState as ECS,
)
from vultron.errors import VultronNotFoundError, VultronValidationError

#: A shared refusal predicate: ``(persistence, case, actor_id, embargo_id)``
#: to the refusal reason, or ``None`` when the message is admitted.
_RefusalPredicate = Callable[
    [CasePersistence, VulnerabilityCase, str, str], "str | None"
]


class _EmbargoRefusalGuardNode(DataLayerConditionWithPorts):
    """Shared frame of the two read-only refusal guards in this module.

    Reads the case and asks one shared predicate of
    :mod:`vultron.core.services.embargo_lifecycle.pec` why *actor_id*'s
    message about *embargo_id* is refused.  SUCCESS when it is not; FAILURE
    otherwise, with the predicate's reason as the feedback message, so the
    handler reports the refusal.  Read-only, so it sits ahead of the guarded
    commit (CLP-10-009): a message the effect would refuse is never committed,
    and no replica is sent an entry it cannot replay (SYNC-12-001).
    """

    _refusal: ClassVar[_RefusalPredicate]

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self.subject_actor_id = actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        refusal = type(self)._refusal(
            self.datalayer, case, self.subject_actor_id, self.embargo_id
        )
        if refusal is None:
            return Status.SUCCESS
        self.feedback_message = refusal
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class IsWithdrawableEmbargoNode(_EmbargoRefusalGuardNode):
    """Guard that a ``Leave(EmbargoEvent)`` names a withdrawal the case admits.

    Refuses unless *embargo_id* is the embargo in force, the withdrawing
    actor is not the case owner, and its row for that embargo is ``AGREED``
    (MSM-07-010).
    """

    _refusal = staticmethod(embargo_withdrawal_refusal)

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        withdrawing_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id, embargo_id, withdrawing_actor_id, name=name)


class RejectIsNotWithdrawalNode(_EmbargoRefusalGuardNode):
    """Guard that a ``Reject(Invite(EmbargoEvent))`` does not withdraw.

    Refuses a Reject of the embargo in force from the rejecting actor's
    ``AGREED`` row: that would be a withdrawal, and withdrawal is
    ``Leave(EmbargoEvent)`` (MSM-07-004, MSM-07-010).  Every other Reject
    passes.
    """

    _refusal = staticmethod(reject_is_withdrawal_refusal)

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        rejecting_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id, embargo_id, rejecting_actor_id, name=name)


class RecordParticipantWithdrawalNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Record a participant's withdrawal from the embargo in force.

    Calls ``EmbargoLifecycle.record_embargo_withdrawal`` for
    *withdrawing_actor_id*, the message's actor (the tree executes as the
    receiving actor, ADR-0022): its ``AGREED`` row for the embargo in force
    and every open proposal's row it had agreed to become ``DECLINED``, and
    no register entry moves (MSM-07-010).  Returns FAILURE — so the handler
    reports a refusal — when the lifecycle refuses the withdrawal or the case
    is not found.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        withdrawing_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id
        self.withdrawing_actor_id = withdrawing_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        try:
            result = EmbargoLifecycle(
                persistence=self.datalayer
            ).record_embargo_withdrawal(
                case_id=self.case_id,
                actor_id=self.withdrawing_actor_id,
                embargo_id=self.embargo_id,
            )
        except (VultronNotFoundError, VultronValidationError) as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.feedback_message = (
            f"Recorded withdrawal of '{self.withdrawing_actor_id}' from"
            f" embargo '{self.embargo_id}' on case '{self.case_id}'"
            f" ({len(result.participant_changes)} consent row change(s))"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class WithdrawEmbargoLifecycleNode(_EmbargoLifecycleNode):
    """Record the executing actor's own withdrawal (the trigger's manager arm).

    A CASE_MANAGER that is a signatory and not the case owner withdraws by
    writing its own consent and committing the ``Leave(EmbargoEvent)``; any
    other participant sends the Leave to the CASE_MANAGER and writes nothing
    (EP-09-008).  Moves no register entry (MSM-07-010).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(result_out=result_out, name=name)
        self._case_id_value = case_id
        self._embargo_id = embargo_id

    def _case_id(self) -> str:
        return self._case_id_value

    def _transition(
        self,
        lifecycle: EmbargoLifecycle,
        actor_id: str,
    ) -> EmbargoLifecycleResult:
        return lifecycle.record_embargo_withdrawal(
            case_id=self._case_id_value,
            actor_id=actor_id,
            embargo_id=self._embargo_id,
        )


class ApplyEmbargoWithdrawalFromLedgerNode(_EmbargoRelayEffectNode):
    """Replay a ``Leave(EmbargoEvent)`` the CASE_MANAGER committed (MSM-07-010).

    Delegates to :class:`RecordParticipantWithdrawalNode` for the entry's
    actor, the operation the CASE_MANAGER ran after its commit: the actor's
    row for the embargo in force and its agreed open proposals' rows become
    ``DECLINED``.  The withdrawing participant's own replica is among the
    fan-out's recipients, because the commit precedes the effect that makes
    it inactive, so it learns its own withdrawal here.

    The CASE_MANAGER commits only a withdrawal its guard admitted, so a
    replica whose row for the embargo is no longer ``AGREED`` — a repeat of
    this entry — or whose case no longer holds the embargo as active (a
    later teardown applied first) has nothing left to apply, and replays
    the entry as a no-op rather than blocking the persist (SYNC-12-001).  An
    actor with no participant record here is skipped (Regime 2, ADR-0087).
    """

    def update(self) -> Status:
        entry = self._get_entry()
        snapshot = entry.payload_snapshot
        resolved = self._resolve(snapshot.get("object"))
        if isinstance(resolved, Status):
            return resolved
        case, embargo_id = resolved
        assert self.datalayer is not None
        actor_id = _extract_id_from_field(snapshot.get("actor"))
        if not actor_id:
            self.feedback_message = (
                f"Leave(EmbargoEvent) on case '{case.id_}' names no actor"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        row = participant_consent_row(
            self.datalayer, case, actor_id, embargo_id
        )
        if row is None:
            self.feedback_message = (
                f"no participant record for '{actor_id}' on case"
                f" '{case.id_}' — skipping (partial replica)"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        if embargo_id != case.active_embargo_id or row is ECS.DECLINED:
            # A repeat of this entry, or a later teardown applied first.
            self.feedback_message = (
                f"Withdrawal of '{actor_id}' from embargo '{embargo_id}' on"
                f" case '{case.id_}' is already applied here — nothing to"
                " replay"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        if row is not ECS.AGREED:
            # The CASE_MANAGER admitted the Leave from an AGREED row, so this
            # replica's row diverges from it.  Not repaired here (#4294 makes
            # replay a copy); logged so the divergence is not mistaken for a
            # repeat, and not failed, so later entries are not blocked.
            self.feedback_message = (
                f"'{actor_id}' is {row.value} on embargo '{embargo_id}' of"
                f" case '{case.id_}' here, but the CASE_MANAGER admitted its"
                " withdrawal from an AGREED row — replica diverges; not"
                " replayed"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        return self._delegate(
            RecordParticipantWithdrawalNode(
                case_id=case.id_,
                embargo_id=embargo_id,
                withdrawing_actor_id=actor_id,
            )
        )


__all__ = [
    "ApplyEmbargoWithdrawalFromLedgerNode",
    "IsWithdrawableEmbargoNode",
    "RecordParticipantWithdrawalNode",
    "RejectIsNotWithdrawalNode",
    "WithdrawEmbargoLifecycleNode",
]
