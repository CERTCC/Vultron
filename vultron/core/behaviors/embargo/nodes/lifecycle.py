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

"""Embargo state machine and lifecycle transition nodes."""

from enum import Enum, auto
from typing import Self, cast

from py_trees.common import Status

from vultron.core.behaviors.embargo.decided_entries import (
    EMBARGO_DECISION_KEY,
    commit_and_apply_decision,
    decide_on_stage,
)
from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.embargo.nodes.terminate import (  # noqa: F401
    SendTerminateEmbargoActivityNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    RegisterStep,
    RegisterStepKind,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    EmbargoLifecycleResult,
    TransitionMode,
)
from vultron.core.services.embargo_lifecycle.staged_persistence import (
    StagedCasePersistence,
)
from vultron.errors import (
    BtNodePreconditionError,
    VultronBTInternalError,
    VultronEntryRefusedError,
    VultronError,
    VultronNotFoundError,
)


class _CopyMode(Enum):
    """How a lifecycle node writes under the copy model (ADR-0124)."""

    #: Decide only; :class:`CommitEmbargoDecisionNode` commits and applies.
    DECIDE = auto()
    #: The act's entry is already committed (intake, ADR-0111): decide, then
    #: commit the consent-row entries and apply.
    APPLY = auto()


class _EmbargoLifecycleNode(DataLayerActionWithPorts, StateWriteCapable):
    """Base node for EmbargoLifecycle strict-mode transitions.

    1. ``ReadEmStateNode`` reads ``em_state`` → ``result_out["em_before"]``.
    2. The subclass ``_transition()`` calls the service.

    By default the service writes directly (EMB-18-001).  Under the copy
    model (ADR-0124, CLP-07-013) it runs on a staged store, so it only
    decides; ``decide_on_stage`` turns the decision into the act's register
    step (:meth:`_register_step`) and one entry per changed consent row.
    :meth:`deciding` hands it to ``CommitEmbargoDecisionNode`` in
    ``result_out[EMBARGO_DECISION_KEY]``; :meth:`applying_after` commits the
    rows and applies here, for an act intake already committed.
    """

    def __init__(
        self, result_out: dict[str, object], name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._result_out = result_out
        self._copy_mode: _CopyMode | None = None
        self._cause_id: str | None = None

    def deciding(self) -> Self:
        """Decide only, for a commit node that commits the act first."""
        self._copy_mode = _CopyMode.DECIDE
        return self

    def applying_after(self, cause_id: str) -> Self:
        """Decide, commit the rows, apply; *cause_id* is the committed act."""
        self._copy_mode = _CopyMode.APPLY
        self._cause_id = cause_id
        return self

    def _case_id(self) -> str:
        raise NotImplementedError

    def _transition(
        self,
        _lifecycle: EmbargoLifecycle,
        _actor_id: str,
    ) -> EmbargoLifecycleResult:
        raise NotImplementedError

    def _answer(self, _actor_id: str) -> ConsentRowChange | None:
        """The row the act's own activity states, for a participant's answer.

        ``None``, the default, for an act that is not an answer.
        """
        return None

    def _register_step(self) -> RegisterStep | None:
        """The register step the act's own activity carries.

        ``None``, the default, for an act that moves no register entry (a
        participant's consent).  Raises a ``VultronError`` when the step
        cannot be named, which refuses the act.
        """
        return None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        self._result_out.pop(EMBARGO_DECISION_KEY, None)

        # AC-1: read em_state via ReadEmStateNode, not inline service code.
        try:
            read_case_em_state(
                self.datalayer, self._case_id(), self._result_out
            )
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE

        if self._copy_mode is not None:
            return self._decide()

        lifecycle = EmbargoLifecycle(persistence=self.datalayer)
        try:
            result = self._transition(lifecycle, self.actor_id)
        except VultronError as exc:
            self._result_out["error"] = exc
            self.feedback_message = str(exc)
            return Status.FAILURE

        self._result_out["lifecycle_result"] = result
        self._result_out["em_after"] = result.em_after

        return Status.SUCCESS

    def _decide(self) -> Status:
        """Decide on a staged store; hand the decision on, or commit and apply."""
        assert self.datalayer is not None
        assert self.actor_id is not None
        staged = StagedCasePersistence(self.datalayer)
        try:
            result = self._transition(
                EmbargoLifecycle(persistence=staged), self.actor_id
            )
            decision = decide_on_stage(
                self.datalayer,
                staged,
                self._case_id(),
                self._register_step(),
                self._answer(self.actor_id),
            )
        except VultronBTInternalError:
            raise
        except VultronError as exc:
            self._result_out["error"] = exc
            self.feedback_message = str(exc)
            return Status.FAILURE
        self._result_out["lifecycle_result"] = result
        self._result_out["em_after"] = result.em_after
        if self._copy_mode is _CopyMode.DECIDE:
            self._result_out[EMBARGO_DECISION_KEY] = decision
            self.feedback_message = (
                f"Decided {len(decision.rows)} consent row(s) beyond the act"
                f" on case '{self._case_id()}'"
            )
            return Status.SUCCESS
        assert self._cause_id is not None
        try:
            commit_and_apply_decision(
                datalayer=cast(CaseOutboxPersistence, self.datalayer),
                decision=decision,
                trigger_activity=self._require_trigger_activity_port(),
                actor_id=self.actor_id,
                cause_id=self._cause_id,
            )
        except VultronEntryRefusedError as exc:
            self._result_out["error"] = exc
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self.feedback_message = f"Applied {len(decision.rows)} row entr(ies)"
        return Status.SUCCESS


class ProposeEmbargoLifecycleNode(_EmbargoLifecycleNode):
    """Apply STRICT propose/counter-propose transition.

    ``proposer_id`` names the actor whose terms these are when the executing
    actor is not the proposer: the CASE_MANAGER adjudicating a received
    proposal runs this node in its own store (EP-09-001) but the consent
    ``propose_embargo`` records — proposing terms is accepting them
    (ADR-0093) — belongs to the participant that proposed, never to the
    manager.  Absent, the executing actor is the proposer (the trigger side).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        result_out: dict[str, object],
        name: str | None = None,
        *,
        proposer_id: str | None = None,
        embargo: EmbargoEvent | None = None,
    ) -> None:
        super().__init__(result_out=result_out, name=name)
        self._case_id_value = case_id
        self._embargo_id = embargo_id
        self._proposer_id = proposer_id
        self._embargo = embargo

    def _register_step(self) -> RegisterStep:
        """``PROPOSE`` with the embargo inline: *embargo*, or the stored one.

        Raises:
            VultronNotFoundError: no embargo to carry; the proposal is refused.
        """
        embargo = self._embargo
        if embargo is None:
            assert self.datalayer is not None
            stored = self.datalayer.read(self._embargo_id)
            if not isinstance(stored, EmbargoEvent):
                raise VultronNotFoundError("EmbargoEvent", self._embargo_id)
            embargo = stored
        return RegisterStep(kind=RegisterStepKind.PROPOSE, embargo=embargo)

    def _case_id(self) -> str:
        return self._case_id_value

    def _transition(
        self,
        lifecycle: EmbargoLifecycle,
        actor_id: str,
    ) -> EmbargoLifecycleResult:
        return lifecycle.propose_embargo(
            case_id=self._case_id_value,
            embargo_id=self._embargo_id,
            actor_id=(
                self._proposer_id
                if self._proposer_id is not None
                else actor_id
            ),
            transition_mode=TransitionMode.STRICT,
        )


class AcceptEmbargoLifecycleNode(_EmbargoLifecycleNode):
    """Record the executing actor's ``Accept(Invite(EmbargoEvent))``.

    The sender's own consent, the case owner's included (ADR-0122): it moves
    no register entry.  The owner's activation is
    ``CommitAndApplyEmbargoActivationNode`` (``activation_commit.py``).
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
        return lifecycle.accept_embargo_invite(
            case_id=self._case_id_value,
            embargo_id=self._embargo_id,
            actor_id=actor_id,
        )

    def _answer(self, actor_id: str) -> ConsentRowChange:
        return ConsentRowChange.answer(
            embargo_id=self._embargo_id, actor_id=actor_id, accept=True
        )


class RejectEmbargoLifecycleNode(_EmbargoLifecycleNode):
    """Record the executing actor's ``Reject(Invite(EmbargoEvent))``.

    The sender's own consent, the case owner's included (MSM-07-004,
    ADR-0122): it declines the named embargo's row only, and never withdraws
    from the embargo in force — that is ``WithdrawEmbargoLifecycleNode``
    (MSM-07-010).  It moves no register entry;
    the owner's rejection of a proposal is
    ``RejectEmbargoProposalLifecycleNode`` (``owner_decision.py``).
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
        return lifecycle.record_embargo_rejection(
            case_id=self._case_id_value,
            actor_id=actor_id,
            embargo_id=self._embargo_id,
        )

    def _answer(self, actor_id: str) -> ConsentRowChange:
        return ConsentRowChange.answer(
            embargo_id=self._embargo_id, actor_id=actor_id, accept=False
        )
