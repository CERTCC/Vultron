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

"""The case owner's Reject of an open embargo proposal (EP-08-003).

:class:`OwnerRejectionAppliesNode` trial-applies the owner's
``Reject(EmbargoEvent, target=Case)`` (ER or EJ, ADR-0122) among the
received tree's guards, with the termination it causes after disclosure
(EMB-04-002); :class:`DecideRejectedEmbargoProposalNode` applies the
``REJECT`` step as the CASE_MANAGER (a replica copies the committed step,
``activation_effect.py``); :class:`EmbargoOutlivesDisclosureNode` tells,
after that step, that the CASE_MANAGER must now terminate the embargo in
the same act (MSM-07-009).  The P/X/A abandonment of open
proposals (EMB-16-001) is the CASE_MANAGER's decision, not an owner's
Reject, and lives in :mod:`.abandon`.

Extracted from lifecycle.py to keep that module under the BTND-07-004
500-line limit.
"""

from py_trees.common import Status

from vultron.core.behaviors.embargo.copy_commit import (
    read_embargo_case_file,
    trial_apply,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.narrative_log import log_em_transition
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.embargo_apply import (
    EmbargoChange,
    RegisterStep,
    RegisterStepKind,
)
from vultron.core.models.embargo_termination import ThreatSignalTermination
from vultron.core.predicates.embargo import (
    embargo_outlives_disclosure,
    rejection_ends_embargo,
)
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    decide_termination,
)
from vultron.errors import VultronError


class DecideRejectedEmbargoProposalNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Apply the case owner's rejection of an open proposal (ER / EJ, EP-08-003).

    The effect of ``Reject(EmbargoEvent, target=Case)``, which only the case
    owner sends (ADR-0122); the received tree's sender guard has already
    established that.  Calls ``EmbargoLifecycle.reject_embargo_proposal``,
    which drives ``PROPOSED → NONE`` or ``REVISE → ACTIVE`` — or, while
    another proposal stays open, only rejects this one (EP-08-001).  It writes
    no consent: a participant's refusal of terms, the owner's included, is a
    ``Reject(Invite(EmbargoEvent))``.  The received path runs it in the
    CASE_MANAGER's store; a replica copies the committed entry instead
    (CM-23-016, ADR-0124).

    With P/X/A set, rejecting the last revision leaves the prior terms in
    force only until :class:`EmbargoOutlivesDisclosureNode`'s termination
    later in the same act (EMB-04-002, MSM-07-009).

    Returns SUCCESS and changes nothing when the embargo is no longer an
    open proposal (already decided), so a repeated Reject is idempotent.
    Returns FAILURE when the case cannot be read or the lifecycle refuses
    the transition.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        if self.embargo_id not in case.proposed_embargo_ids:
            self.feedback_message = (
                f"Embargo '{self.embargo_id}' is not an open proposal of case"
                f" '{self.case_id}' — nothing to decide"
            )
            return Status.SUCCESS

        try:
            result = EmbargoLifecycle(
                persistence=self.datalayer
            ).reject_embargo_proposal(
                case_id=self.case_id,
                embargo_id=self.embargo_id,
                actor_id=self.actor_id,
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        log_em_transition(
            self.logger,
            self.actor_id or "<unknown>",
            self.case_id,
            result.em_before,
            result.em_after,
        )
        self.feedback_message = (
            f"Owner rejected embargo '{self.embargo_id}' on case"
            f" '{self.case_id}' (EM {result.em_before} → {result.em_after})"
        )
        return Status.SUCCESS


class OwnerRejectionAppliesNode(DataLayerConditionWithPorts):
    """Guard: the owner's rejection, and any termination it causes, apply.

    The CASE_MANAGER decides the act among the guards, before the guarded
    commit (ADR-0124, SYNC-12-001): the ``REJECT`` step of ``embargo_id``,
    then, when :func:`~vultron.core.predicates.embargo.rejection_ends_embargo`
    holds, the ``TERMINATE`` step its own ``Remove`` will carry, decided by
    :func:`~vultron.core.services.embargo_lifecycle.decide_termination` with
    the threat signals the case carries (EMB-04-002, EMB-13-005).  Both are
    applied in order to a copy of the case file through the one apply
    function.  FAILURE when the decision or either step is refused, so the
    act is refused before its entry is committed and a refused termination
    commits neither entry (MSM-07-009).  Read-only.
    """

    def __init__(
        self, case_id: str, embargo_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        changes: list[EmbargoChange] = [
            RegisterStep(kind=RegisterStepKind.REJECT, embargo=self.embargo_id)
        ]
        try:
            if rejection_ends_embargo(case, self.embargo_id):
                changes.append(
                    decide_termination(
                        self.datalayer, case, ThreatSignalTermination(), None
                    )
                )
            trial_apply(
                read_embargo_case_file(self.datalayer, self.case_id), changes
            )
        except VultronError as exc:
            self.feedback_message = (
                f"the owner's rejection of embargo '{self.embargo_id}'"
                f" records nothing on case '{self.case_id}': {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


class EmbargoOutlivesDisclosureNode(DataLayerConditionWithPorts):
    """True when the prior terms stand with P/X/A set (EMB-04-002).

    Read after the owner's ``REJECT`` step, in the same act: SUCCESS when
    an embargo is in force, no proposal is open and CS is public, exploited
    or attacked (:func:`~vultron.core.predicates.embargo.embargo_outlives_disclosure`).
    The rejection then decided the last revision after disclosure, and
    returning to the prior terms is not allowed, so the CASE_MANAGER
    terminates the embargo before the act ends (MSM-07-009).  FAILURE in
    every other case.  Read-only.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        if embargo_outlives_disclosure(case):
            self.feedback_message = (
                f"the prior terms of case '{self.case_id}' stand with P/X/A"
                " set: the embargo ends (ET) in the same act (EMB-04-002)"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        return Status.FAILURE
