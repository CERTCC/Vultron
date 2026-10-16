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
- :class:`EmbargoWithdrawalAppliesNode` — the received tree's decision
  guard: the CASE_MANAGER decides the withdrawal on a staged store before
  intake commits the Leave (ADR-0124).
- :class:`RecordParticipantWithdrawalNode` — the CASE_MANAGER's effect.
- :class:`WithdrawEmbargoLifecycleNode` — the trigger's CASE_MANAGER arm.
- :class:`ApplyEmbargoWithdrawalFromLedgerNode` — the replica slot
  (EP-09-007, RSH-08-004).

Under the copy model (ADR-0124, CLP-07-013) the ``Leave`` is its own entry
and carries no row: each row the withdrawal declines (the sender's row for
the embargo in force, and every open proposal's row it had agreed to) is
committed after it as the CASE_MANAGER's own ``Update(EmbargoConsent)``
entry, which every replica copies (``ApplyEmbargoConsentFromLedgerNode``).

Each check calls the shared predicates in
:mod:`vultron.core.services.embargo_lifecycle.pec`, which the lifecycle's own
refusal also calls, so the guard and the write cannot drift.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.embargo.decided_entries import (
    EmbargoDecision,
    decide_embargo_act,
)
from vultron.core.behaviors.embargo.nodes.answer_record import (
    EmbargoDecisionAppliesNode,
    case_manager_decision_guard,
)
from vultron.core.behaviors.embargo.nodes.lifecycle import (
    _EmbargoLifecycleNode,
)
from vultron.core.behaviors.embargo.nodes.proposal import (
    _RecordReceivedConsentNode,
)
from vultron.core.behaviors.embargo.nodes.relay_effect import (
    _EmbargoRelayEffectNode,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    EmbargoLifecycleResult,
    embargo_withdrawal_refusal,
    reject_is_withdrawal_refusal,
)
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.errors import VultronNotFoundError, VultronValidationError


def is_ledgered_activity(
    datalayer: CasePersistence, case_id: str, activity_id: str
) -> bool:
    """``True`` when *case_id*'s ledger already records *activity_id*."""
    return any(
        entry.log_object_id == activity_id
        for entry in recorded_entries_for_case(case_id=case_id, dl=datalayer)
    )


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

        try:
            refusal = self._refusal(self.datalayer, case)
        except VultronNotFoundError as exc:
            # A participant holds a row for every register entry (ADR-0122),
            # so a missing one is a defect in this store; refuse with it.
            refusal = str(exc)
        if refusal is None:
            return Status.SUCCESS
        self.feedback_message = refusal
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _refusal(
        self, datalayer: CasePersistence, case: VulnerabilityCase
    ) -> str | None:
        """The shared predicate's refusal reason, or ``None``."""
        raise NotImplementedError


class IsWithdrawableEmbargoNode(_EmbargoRefusalGuardNode):
    """Guard that a ``Leave(EmbargoEvent)`` names a withdrawal the case admits.

    Refuses unless *embargo_id* is the embargo in force, the withdrawing
    actor is not the case owner, and its row for that embargo is ``AGREED``
    (MSM-07-010).

    A **redelivery** of a Leave the case's ledger already records (the same
    *activity_id*) is not a new withdrawal and not a refusal (HP-01-003), but
    it must change nothing: the guard sets :attr:`is_redelivery` and fails,
    so nothing downstream runs, and the handler reports the run as
    ``SKIPPED``.  A new Leave from a row the earlier one already declined is
    still refused (MSM-07-010).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        withdrawing_actor_id: str,
        activity_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id, embargo_id, withdrawing_actor_id, name=name)
        self.activity_id = activity_id
        self.is_redelivery = False
        """``True`` when the last run found this Leave already ledgered: a
        benign no-op, not a refusal."""

    def update(self) -> Status:
        self.is_redelivery = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if is_ledgered_activity(
            self.datalayer, self.case_id, self.activity_id
        ):
            self.is_redelivery = True
            self.feedback_message = (
                f"Leave '{self.activity_id}' is already recorded for case"
                f" '{self.case_id}' — redelivery, nothing to apply (HP-01-003)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return super().update()

    def _refusal(
        self, datalayer: CasePersistence, case: VulnerabilityCase
    ) -> str | None:
        return embargo_withdrawal_refusal(
            datalayer, case, self.subject_actor_id, self.embargo_id
        )


class RejectIsNotWithdrawalNode(_EmbargoRefusalGuardNode):
    """Guard that a ``Reject(Invite(EmbargoEvent))`` does not withdraw.

    Refuses a Reject of the embargo in force from the rejecting actor's
    ``AGREED`` row: that would be a withdrawal, and withdrawal is
    ``Leave(EmbargoEvent)`` (MSM-07-004, MSM-07-010).  Every other Reject
    passes.
    """

    def _refusal(
        self, datalayer: CasePersistence, case: VulnerabilityCase
    ) -> str | None:
        return reject_is_withdrawal_refusal(
            datalayer, case, self.subject_actor_id, self.embargo_id
        )

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        rejecting_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id, embargo_id, rejecting_actor_id, name=name)


def decide_withdrawal(
    datalayer: CasePersistence,
    *,
    case_id: str,
    embargo_id: str,
    actor_id: str,
) -> EmbargoDecision:
    """The decision *actor_id*'s withdrawal from *embargo_id* makes, staged.

    ``EmbargoLifecycle.record_embargo_withdrawal`` runs on a staged copy of
    *datalayer*, so nothing is written.  The ``Leave`` moves no register
    entry and carries no row, so the decision's act is ``None`` and every
    row it declines is one of its :attr:`~EmbargoDecision.rows`
    (MSM-07-010, ADR-0124).

    Raises:
        VultronError: the lifecycle refuses the withdrawal.
        VultronBTInternalError: the entries do not carry what it wrote.
    """

    def _decide(staged: CasePersistence) -> object:
        return EmbargoLifecycle(persistence=staged).record_embargo_withdrawal(
            case_id=case_id, actor_id=actor_id, embargo_id=embargo_id
        )

    return decide_embargo_act(datalayer, case_id, _decide)


class EmbargoWithdrawalAppliesNode(EmbargoDecisionAppliesNode):
    """Guard: the CASE_MANAGER's decision of a received withdrawal applies.

    Runs :func:`decide_withdrawal` and writes nothing, so a Leave the
    lifecycle would refuse, or whose row entries would not apply, is refused
    before intake commits it (ADR-0122: for a received act the trial runs
    among its guards).  A decision fault raises.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        withdrawing_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id, name=name)
        self.embargo_id = embargo_id
        self.withdrawing_actor_id = withdrawing_actor_id

    def _decide(self, datalayer: CasePersistence) -> EmbargoDecision:
        return decide_withdrawal(
            datalayer,
            case_id=self.case_id,
            embargo_id=self.embargo_id,
            actor_id=self.withdrawing_actor_id,
        )

    def _act(self) -> str:
        return (
            f"'{self.withdrawing_actor_id}''s withdrawal from embargo"
            f" '{self.embargo_id}'"
        )


def case_manager_admits_withdrawal_guard(
    case_id: str, embargo_id: str, withdrawing_actor_id: str
) -> py_trees.behaviour.Behaviour:
    """Precondition guard: at the CASE_MANAGER, the withdrawal applies."""
    return case_manager_decision_guard(
        "EmbargoWithdrawalApplies",
        case_id,
        EmbargoWithdrawalAppliesNode(
            case_id=case_id,
            embargo_id=embargo_id,
            withdrawing_actor_id=withdrawing_actor_id,
        ),
    )


class RecordParticipantWithdrawalNode(_RecordReceivedConsentNode):
    """Record a participant's withdrawal from the embargo in force.

    Intake has committed the ``Leave`` (ADR-0111).  The node decides the
    withdrawal for *withdrawing_actor_id*, the message's actor (the tree
    executes as the receiving CASE_MANAGER, ADR-0022), with
    :func:`decide_withdrawal`: its ``AGREED`` row for the embargo in force
    and every open proposal's row it had agreed to become ``DECLINED``, and
    no register entry moves (MSM-07-010).  Each declined row is then
    committed as the CASE_MANAGER's own ``Update(EmbargoConsent)`` entry,
    after the Leave, and applied by copying (ADR-0124, CLP-07-013).

    Returns FAILURE — so the handler reports a refusal — when the lifecycle
    refuses the withdrawal or the case is not found.  The decision and the
    commit's trial run on the same store in one tick, so the trial cannot
    refuse what the decision wrote.  A failed commit raises (BT-14-001).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        withdrawing_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id=case_id, embargo_id=embargo_id, name=name)
        self.withdrawing_actor_id = withdrawing_actor_id

    def _decide(self, actor_id: str) -> EmbargoDecision:
        assert self.datalayer is not None
        return decide_withdrawal(
            self.datalayer,
            case_id=self.case_id,
            embargo_id=self.embargo_id,
            actor_id=actor_id,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f

        try:
            decision = self._record(self.withdrawing_actor_id)
        except (VultronNotFoundError, VultronValidationError) as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.feedback_message = (
            f"Recorded withdrawal of '{self.withdrawing_actor_id}' from"
            f" embargo '{self.embargo_id}' on case '{self.case_id}'"
            f" ({len(decision.rows)} declined row entr(ies))"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class WithdrawEmbargoLifecycleNode(_EmbargoLifecycleNode):
    """Record the executing actor's own withdrawal (the trigger's manager arm).

    A CASE_MANAGER that is a signatory and not the case owner withdraws:
    the trigger tree runs this node ``deciding()``, on a staged store, and
    ``CommitEmbargoDecisionNode`` commits the ``Leave(EmbargoEvent)``, then
    each row it declines as its own ``Update(EmbargoConsent)`` entry, and
    applies them by copying (ADR-0124).  Any other participant sends the
    Leave to the CASE_MANAGER and writes nothing (EP-09-008).  Moves no
    register entry (MSM-07-010).
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
    """Store a ``Leave(EmbargoEvent)`` the CASE_MANAGER committed (MSM-07-010).

    The Leave carries no row and moves no register entry, so this slot
    writes nothing but the embargo it names, if absent.  Each row the
    withdrawal declines follows as the CASE_MANAGER's own
    ``Update(EmbargoConsent)`` entry, which the consent slot copies
    (``ApplyEmbargoConsentFromLedgerNode``, ADR-0124, CM-23-016); the slot
    re-runs no lifecycle logic.  The withdrawing participant's own replica
    is among the recipients of the Leave and of every row entry, since each
    is committed before the CASE_MANAGER applies the rows that make it
    inactive, so it learns its own withdrawal from the same entries.
    Regime 2 (ADR-0087): a replica with no copy of the case skips it.
    """

    def update(self) -> Status:
        return self._store_only(
            self._get_entry().payload_snapshot.get("object")
        )


__all__ = [
    "ApplyEmbargoWithdrawalFromLedgerNode",
    "EmbargoWithdrawalAppliesNode",
    "IsWithdrawableEmbargoNode",
    "RecordParticipantWithdrawalNode",
    "RejectIsNotWithdrawalNode",
    "WithdrawEmbargoLifecycleNode",
    "case_manager_admits_withdrawal_guard",
    "decide_withdrawal",
]
