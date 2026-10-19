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

"""The CASE_MANAGER's activation: decide, commit the entries, then apply.

The case owner's ``Accept(EmbargoEvent, target=Case)`` activates a proposal
(ADR-0122).  As the CASE_MANAGER, :class:`CommitAndApplyEmbargoActivationNode`
follows the copy model (ADR-0124, #4294):

1. **Decide** —
   :meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.decide_activation`
   checks the proposal is open and P/X/A is clear (EMB-02-002), decides the
   EP-05-001 arm and names every change; nothing is written.
2. **Trial, commit, apply** —
   :func:`~vultron.core.behaviors.embargo.copy_commit.commit_and_apply_embargo_entries`
   trial-applies every change through the one apply function, commits the
   entries in order and only then saves the result:

   - the ``Accept``, which is the whole ``ACTIVATE`` register step, the
     ``SUPERSEDE`` of the embargo in force included, and states the owner's
     ``AGREED`` row (CLP-07-013, MSM-07-008).  On the trigger path the node
     builds and commits it; on the received path intake committed it before
     the guards admitted the act (ADR-0111), so it has no commit step here;
   - one CASE_MANAGER ``Update(EmbargoConsent)`` per ``CARRY_OVER`` row
     (EP-05-001), after the ``Accept``.

A commit that fails leaves every change whose entry did not commit unwritten
(CLP-07-013): with the ``Accept`` unrecorded, the register, EM and the consent
rows are as they were.
"""

from functools import partial
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)
from vultron.core.behaviors.embargo.copy_commit import (
    PlannedEmbargoEntry,
    commit_and_apply_embargo_entries,
    consent_row_entry,
    read_embargo_case_file,
    trial_apply,
)
from vultron.core.behaviors.embargo.nodes.activation_effect import (
    EMBARGO_ACTIVATION_SEMANTIC_TYPE,
)
from vultron.core.behaviors.embargo.nodes.manager_commit import (
    EmbargoActivityBuilder,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.narrative_log import log_em_transition
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.embargo_apply import ConsentRowChange
from vultron.core.models.events.base import VultronEvent
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.services.embargo_lifecycle import (
    ActivationDecision,
    EmbargoLifecycle,
    EmbargoLifecycleResult,
    ParticipantConsentChange,
)
from vultron.errors import (
    BtNodePreconditionError,
    VultronError,
    VultronWiringError,
)


class CommitAndApplyEmbargoActivationNode(
    _CommitCaseManagerActivityBase, StateWriteCapable
):
    """Activate a proposal as the CASE_MANAGER, committing before writing.

    *builder* is the trigger use case's ``Accept`` builder: the node commits
    the ``Accept`` it builds, addressed to nobody, since every replica
    learns it from the entry (EP-09-007).  ``None`` on the received path,
    where intake has already committed the owner's ``Accept``; the received
    activity on ``/activity`` names the cause of the carry-over entries.

    FAILURE, with the error in ``result_out["error"]`` and nothing committed
    or written, when the decision or the trial apply refuses the activation,
    or the Accept's commit frame fails because the case vanished after the
    decision.  A commit that fails raises, as every CASE_MANAGER commit does
    (BT-14-001), and so does a miswired tree (no factory, or no received
    activity to name as the carry-overs' cause).  Either way only the
    changes whose entries committed are written.  On SUCCESS ``result_out``
    holds ``em_before``, ``em_after`` and the ``lifecycle_result`` the
    trigger use case reports.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        result_out: dict[str, object],
        builder: EmbargoActivityBuilder | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(
            case_id=case_id,
            semantic_type=EMBARGO_ACTIVATION_SEMANTIC_TYPE,
            notify_participants=False,
            name=name,
        )
        self._embargo_id = embargo_id
        self._result_out = result_out
        self._builder = builder
        self._event: object | None = None
        self._accept_id: str | None = None

    def initialise(self) -> None:
        super().initialise()
        self._event = self._try_get_input("activity")
        self._accept_id = None

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        assert self._builder is not None  # only the trigger path commits
        activity_id, blob = self._builder(to)
        self._accept_id = activity_id
        return activity_id, blob

    def _commit_accept(self) -> None:
        """Queue and commit the ``Accept``: the base frame's ``update()``.

        Raises:
            BtNodePreconditionError: the frame returned FAILURE (the case
                vanished after the decision), so the entry did not commit.
        """
        if super().update() != Status.SUCCESS:
            raise BtNodePreconditionError(
                f"{self.name}: the Accept of embargo '{self._embargo_id}' on"
                f" case '{self._case_id}' did not commit:"
                f" {self.feedback_message}"
            )

    def _cause_id(self) -> str:
        """The ``Accept`` the carry-over entries follow."""
        if self._builder is not None:
            assert self._accept_id is not None  # committed first
            return self._accept_id
        event = self._event
        if not isinstance(event, VultronEvent):
            raise VultronWiringError(
                f"{self.name}: no received Accept on the blackboard to name"
                " as the cause of the carry-over entries (ARCH-15-001)"
            )
        return event.activity_id

    def _commit_row(self, change: ConsentRowChange) -> None:
        commit = consent_row_entry(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            trigger_activity=self._require_trigger_activity_port(),
            actor_id=cast(str, self.actor_id),
            case_id=self._case_id,
            change=change,
            cause_id=self._cause_id(),
        ).commit
        assert commit is not None  # a consent-row entry always commits
        commit()

    def _planned(
        self, decision: ActivationDecision
    ) -> list[PlannedEmbargoEntry]:
        accept = self._commit_accept if self._builder is not None else None
        return [
            PlannedEmbargoEntry(change=decision.step, commit=accept),
            *(
                [PlannedEmbargoEntry(change=decision.owner_agreement)]
                if decision.owner_agreement is not None
                else []
            ),
            *(
                PlannedEmbargoEntry(
                    change=row, commit=partial(self._commit_row, row)
                )
                for row in decision.carry_overs
            ),
        ]

    def _refuse(self, exc: VultronError) -> Status:
        self._result_out["error"] = exc
        self.feedback_message = str(exc)
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        dl = cast(CaseOutboxPersistence, self.datalayer)
        try:
            before = read_embargo_case_file(dl, self._case_id)
            decision = EmbargoLifecycle(persistence=dl).decide_activation(
                before, self._embargo_id
            )
            # The helper trial-applies every entry before the first commit,
            # so a refused step commits nothing.  A commit that fails raises
            # past this: it is not a refusal (BT-14-001).
            commit_and_apply_embargo_entries(
                dl, self._case_id, self._planned(decision)
            )
        except VultronWiringError:
            raise  # a composition fault, never a refusal (ARCH-15-001)
        except VultronError as exc:
            return self._refuse(exc)

        participant_ids = {
            actor_id: record.id_
            for actor_id, record in before.participants.items()
        }
        self._result_out["em_before"] = decision.em_before
        self._result_out["em_after"] = decision.em_after
        self._result_out["lifecycle_result"] = EmbargoLifecycleResult(
            em_before=decision.em_before,
            em_after=decision.em_after,
            case_changed=True,
            case_embargo_changed=True,
            participant_changes=[
                ParticipantConsentChange(
                    participant_id=participant_ids[row.actor_id],
                    embargo_id=row.row.embargo_id,
                    consent_before=before.participants[row.actor_id]
                    .consent_for(row.row.embargo_id)
                    .value,
                    consent_after=row.row.state.value,
                )
                for row in decision.consent_rows
            ],
        )
        self.feedback_message = (
            f"CASE_MANAGER activated embargo '{self._embargo_id}' on case"
            f" '{self._case_id}' after committing its Accept"
            f" ({len(decision.carry_overs)} carry-over entr(ies),"
            f" EM {decision.em_before} → {decision.em_after})"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        log_em_transition(
            self.logger,
            cast(str, self.actor_id),
            self._case_id,
            decision.em_before,
            decision.em_after,
        )
        return Status.SUCCESS


class ActivationAppliesNode(DataLayerConditionWithPorts):
    """Guard: the CASE_MANAGER's decision and trial apply admit the activation.

    The received owner's ``Accept`` is committed by intake before its
    effects run (ADR-0111), so its trial runs here, among the guards: a step
    the register refuses refuses the act, and no entry is committed for it
    (ADR-0124).  Read-only.
    """

    def __init__(
        self, case_id: str, embargo_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        dl = cast(CaseOutboxPersistence, self.datalayer)
        try:
            before = read_embargo_case_file(dl, self._case_id)
            decision = EmbargoLifecycle(persistence=dl).decide_activation(
                before, self._embargo_id
            )
            trial_apply(before, [decision.step, *decision.consent_rows])
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


__all__ = ["ActivationAppliesNode", "CommitAndApplyEmbargoActivationNode"]
