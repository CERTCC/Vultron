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

"""The CASE_MANAGER's termination: decide, commit the ``Remove``, then apply.

The terminate trigger, the end-time paths and the CS ``P``/``X``/``A``
cascades all end the embargo in force through
:class:`CommitAndApplyEmbargoTerminationNode` (BT-19-001).  It follows the
copy model (ADR-0124, #4294):

1. **Decide** —
   :func:`~vultron.core.services.embargo_lifecycle.decide_termination`
   names the embargo in force and resolves the termination (a threat
   signal's signals, an end time that is due); nothing is written.
2. **Trial, commit, apply** —
   :func:`~vultron.core.behaviors.embargo.copy_commit.commit_and_apply_embargo_entries`
   trial-applies the ``TERMINATE`` step through the one apply function,
   commits the ``Remove(EmbargoEvent)`` entry that carries it, and only then
   saves the result.

The ``Remove`` entry is the whole register step, the ``CANCEL`` of every open
proposal included (EP-08-004, ADR-0122): no other entry records a cancel, and
a termination writes no consent row.  A commit that fails therefore leaves
the register, EM and the consent rows as they were, and the queued
``Remove`` is withdrawn from the outbox (#4653), so a retry can still end the
embargo.
"""

from datetime import datetime
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)
from vultron.core.behaviors.embargo.copy_commit import (
    PlannedEmbargoEntry,
    commit_and_apply_embargo_entries,
    read_embargo_case_file,
    trial_apply,
)
from vultron.core.behaviors.embargo.nodes.chosen_cause import (
    ChosenTermination,
    resolve_chosen,
)
from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.embargo.nodes.manager_commit import (
    EMBARGO_TEARDOWN_SEMANTIC_TYPE,
    EmbargoActivityBuilder,
)
from vultron.core.behaviors.narrative_log import log_em_transition
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_apply import RegisterStep
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    TerminationRequest,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycleResult,
    decide_termination,
)
from vultron.errors import (
    BtNodePreconditionError,
    VultronEntryRefusedError,
    VultronError,
)


class CommitAndApplyEmbargoTerminationNode(
    _CommitCaseManagerActivityBase, StateWriteCapable
):
    """End the embargo in force as the CASE_MANAGER, committing first.

    *termination* is how the embargo ends (ADR-0122), a
    :class:`ChosenTermination` read at the write (EMB-14-001); *terminated_at* is the
    time an ``END_TIME_REACHED`` termination is claimed at.  *builder* is
    the trigger use case's own ``Remove`` builder; ``None`` (the end-time
    check and the threat cascades) builds it through the trigger-activity
    factory, carrying the decided termination's what in ``content`` and its
    why, the cause the ``TERMINATED`` entry records (a threat cascade's
    signals included), as ``terminationCause`` (EMB-13-005).  The
    ``Remove`` is addressed to every other participant and never to the
    manager (EMB-19-001, #4112).

    FAILURE, with the error in ``result_out["error"]`` and nothing committed
    or written, when the decision or the trial apply refuses the termination.
    A commit that fails raises, as every CASE_MANAGER commit does
    (BT-14-001); nothing has been written by then.  On SUCCESS
    ``result_out`` holds ``em_before``, ``em_after`` and the
    ``lifecycle_result`` the trigger use case reports.
    """

    def __init__(
        self,
        case_id: str,
        result_out: dict[str, object],
        termination: TerminationRequest | ChosenTermination,
        terminated_at: datetime | None = None,
        builder: EmbargoActivityBuilder | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(
            case_id=case_id,
            semantic_type=EMBARGO_TEARDOWN_SEMANTIC_TYPE,
            notify_participants=True,
            name=name,
        )
        self._result_out = result_out
        self._termination = termination
        self._terminated_at = terminated_at
        self._builder = builder
        self._step: RegisterStep | None = None
        self._ended: VulnerabilityCase | None = None

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        if self._builder is not None:
            return self._builder(to)
        assert self._step is not None  # decided before the commit runs
        assert self.trigger_activity_factory is not None
        recorded = cast(EmbargoTermination, self._step.termination)
        return self.trigger_activity_factory.terminate_embargo(
            embargo_id=self._step.embargo_id,
            case_id=self._case_id,
            actor=cast(str, self.actor_id),
            reason=recorded.reason,
            cause=recorded.cause,
            to=to,
        )

    def _audience_case(self, case: VulnerabilityCase) -> VulnerabilityCase:
        """The case as the termination leaves it.

        The ``Remove`` is committed before the step is applied, but it is
        addressed to the participants the case reaches once the embargo has
        ended, as it was when the write came first.
        """
        return self._ended if self._ended is not None else case

    def _commit_remove(self) -> None:
        """Queue and commit the ``Remove``: the base frame's ``update()``.

        Raises:
            BtNodePreconditionError: the frame returned FAILURE (the case
                vanished after the decision), so the entry did not commit.
        """
        if super().update() != Status.SUCCESS:
            raise BtNodePreconditionError(
                f"{self.name}: the Remove of case '{self._case_id}' did not"
                f" commit: {self.feedback_message}"
            )

    def _refuse(self, exc: VultronError) -> Status:
        self._result_out["error"] = exc
        self.feedback_message = str(exc)
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        dl = cast(CasePersistence, self.datalayer)
        try:
            em_before = read_case_em_state(dl, self._case_id, self._result_out)
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        try:
            step = decide_termination(
                dl,
                case,
                resolve_chosen(self._termination),
                self._terminated_at,
            )
        except VultronError as exc:
            return self._refuse(exc)
        self._step = step
        try:
            # The trial, run here as well so the Remove's audience is the
            # case the step leaves (``_audience_case``).
            before = read_embargo_case_file(dl, self._case_id)
            self._ended = trial_apply(before, [step])[-1].case
        except VultronEntryRefusedError as exc:
            return self._refuse(exc)
        try:
            # The helper repeats the trial on a fresh read, so a case changed
            # since the trial above is still refused before the commit.  A
            # commit that fails raises past this: it is not a refusal
            # (BT-14-001), and nothing has been written by then.
            applied = commit_and_apply_embargo_entries(
                dl,
                self._case_id,
                [PlannedEmbargoEntry(change=step, commit=self._commit_remove)],
            )
        except VultronEntryRefusedError as exc:
            return self._refuse(exc)

        em_after = applied.case.em_state
        self._result_out["em_after"] = em_after
        self._result_out["lifecycle_result"] = EmbargoLifecycleResult(
            em_before=em_before,
            em_after=em_after,
            case_changed=True,
            case_embargo_changed=True,
        )
        self.feedback_message = (
            f"CASE_MANAGER terminated embargo '{step.embargo_id}' on"
            f" case '{self._case_id}' after committing its Remove"
            f" (EM {em_before} → {em_after})"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        log_em_transition(
            self.logger,
            cast(str, self.actor_id),
            self._case_id,
            em_before,
            em_after,
        )
        return Status.SUCCESS


__all__ = ["CommitAndApplyEmbargoTerminationNode"]
