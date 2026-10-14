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

"""Trigger-side behavior tree for create-case workflow."""

import json
from collections.abc import Callable
from typing import Any, cast

import py_trees
from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
)
from vultron.core.behaviors.case.nodes.proposal_ledger import (
    CommitNativeLedgerEntriesNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
    UpdateActorOutbox,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.nodes.port_guard import (
    RequireSyncPortNode,
    RequireWireRenderPortNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.enums.roles import CVDRole
from vultron.errors import VultronNotFoundError


class _CreateCaseRecordNode(DataLayerActionWithPorts, StateWriteCapable):
    """Create and persist VulnerabilityCase; publish case_id to blackboard."""

    def __init__(
        self,
        case_name: str,
        case_content: str,
        report_id: str | None,
        result_out: dict[str, Any],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_name = case_name
        self._case_content = case_content
        self._report_id = report_id
        self._result_out = result_out

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "case_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        case = VulnerabilityCase(
            name=self._case_name,
            content=self._case_content,
            attributed_to=self.actor_id,
        )
        if self._report_id is not None:
            case.vulnerability_reports.append(self._report_id)
        self.datalayer.create(case)
        self._set_output("case_id", case.id_)
        self._result_out["case_id"] = case.id_
        return Status.SUCCESS


class _RegisterCreatorParticipantNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Register CASE_OWNER+CASE_MANAGER participant for the creating actor (CM-02-015)."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self._case_id_bb: str = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            self._case_id_bb = ""

    def update(self) -> Status:
        case_id = self._case_id_bb
        if not case_id:
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        participant = CaseParticipant(
            attributed_to=self.actor_id,
            case_roles=[CVDRole.CASE_OWNER, CVDRole.CASE_MANAGER],
        )
        case = _create_and_attach_participant(
            self.datalayer, participant, case_id, self.actor_id, self.logger
        )
        if case is None:
            return Status.FAILURE
        self.datalayer.save(case)
        return Status.SUCCESS


class _BuildCreateCaseActivityNode(DataLayerActionWithPorts):
    """Create Create(Case) activity and publish activity_id to blackboard."""

    def __init__(
        self,
        activity_builder: Callable[[str], tuple[str, str]],
        result_out: dict[str, Any],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._activity_builder = activity_builder
        self._result_out = result_out

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "activity_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id", "activity_id": "/activity_id"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self._case_id_bb: str = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            self._case_id_bb = ""

    def update(self) -> Status:
        case_id = self._case_id_bb
        if not case_id:
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE

        try:
            activity_id, activity_dict = self._activity_builder(case_id)
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3768
            self.feedback_message = (
                f"CreateCase activity construction failed: {exc}"
            )
            self.logger.error("%s", self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE

        self._set_output("activity_id", activity_id)
        self._result_out["activity"] = json.loads(activity_dict)
        return Status.SUCCESS


class WithdrawUncommittedCaseNode(DataLayerActionWithPorts, StateWriteCapable):
    """Withdraw a new case none of whose creation entries committed.

    Runs only after the queue-then-commit step fails, and always returns
    FAILURE, carrying the reason.  The trigger queues the ``Create`` before
    it commits (ADR-0119), so a case with no entry in the ledger may still
    have its ``Create`` pending in the outbox; one whose outbox write failed
    has nothing queued and nothing committed.  The node
    withdraws it from the outbox first (``outbox_withdraw``); once nothing
    about the case was committed or sent, the case, the participant records
    it names and the ``Create`` are removed, so the case file is as it was
    before the trigger (CLP-07-013).  The report the case was created from
    is not the creation's write and stays.  So do the sealed outbound bodies
    the activity factory kept for the ``Create`` and the genesis activity:
    they are the delivery adapter's bookkeeping, not case-file state, nothing
    queued refers to them, and the core layer has no port to them
    (ARCH-01-001).

    A participant record, the ``Create`` or the case that cannot be deleted
    raises: a withdrawal that leaves part of the case behind is not one.

    Once the genesis entry has committed, the case cannot be withdrawn: the
    ledger records it.  Nor can it once delivery has taken its ``Create``:
    the recipient holds the case.  The node then removes nothing, and the
    failure is surfaced, not prevented, as on the proposal path (CP-09-009).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
        "activity_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id", "activity_id": "/activity_id"}

    def __init__(
        self,
        commit: CommitNativeLedgerEntriesNode,
        outbox_step: UpdateActorOutbox | None,
        name: str | None = None,
    ) -> None:
        """Create the node.

        Args:
            commit: The commit node this one follows; its feedback is the
                reason the creation failed.
            outbox_step: The node that queues the ``Create`` ahead of the
                commit, or ``None`` when the tree queues nothing.  The
                ``Create`` was queued only if that node succeeded.
            name: Node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._commit = commit
        self._outbox_step = outbox_step

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = ""
        self._activity_id_bb = ""
        try:
            self._case_id_bb = self.get_input("case_id")
            self._activity_id_bb = self.get_input("activity_id")
        except (NoDataAvailable, NotImplementedError):
            pass

    def _delete(self, table: str, record_id: str) -> None:
        """Delete one record of the withdrawn case, or raise."""
        assert self.datalayer is not None
        if not self.datalayer.delete(table, record_id):
            raise VultronNotFoundError(table, record_id)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        reason = (
            "its Create could not be queued for delivery"
            if self._outbox_step is not None
            and self._outbox_step.status == Status.FAILURE
            else self._commit.feedback_message or "creation commit failed"
        )
        case, failure = self._require_case(self._case_id_bb)
        if failure is not None:
            # Regime 1: nothing written to withdraw (ADR-0087).  The commit's
            # reason is still the creation's failure, so it is kept.
            self.feedback_message = f"{reason}; {self.feedback_message}"
            return failure
        if recorded_entries_for_case(case_id=case.id_, dl=self.datalayer):
            self.feedback_message = reason
            return Status.FAILURE
        if not self._withdraw_create():
            self.feedback_message = (
                f"{reason}; its Create '{self._activity_id_bb}' was already"
                " taken for delivery, so the case is kept (CP-09-009)"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        for participant_id in case.actor_participant_index.values():
            participant = self.datalayer.read(participant_id)
            if not isinstance(participant, CaseParticipant):
                raise VultronNotFoundError("CaseParticipant", participant_id)
            for status in participant.participant_statuses:
                # A status may be held only inline on its participant, with
                # no row of its own; the participant's deletion removes it.
                self.datalayer.delete("ParticipantStatus", status.id_)
            self._delete("CaseParticipant", participant_id)
        if self._activity_id_bb:
            self._delete("Create", self._activity_id_bb)
        self._delete("VulnerabilityCase", case.id_)
        self.feedback_message = (
            f"{reason}; nothing was committed or sent, so the case was"
            " withdrawn (CLP-07-013)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _withdraw_create(self) -> bool:
        """Take the queued ``Create`` back out of the outbox; ``False`` if gone.

        ``True`` when nothing was queued or the pending ``Create`` was
        withdrawn: the case was sent to no one.
        """
        if (
            self._outbox_step is None
            or self._outbox_step.status != Status.SUCCESS
            or not self._activity_id_bb
        ):
            return True
        assert self.datalayer is not None
        return cast(CaseOutboxPersistence, self.datalayer).outbox_withdraw(
            self._activity_id_bb
        )


def create_case_trigger_bt(
    *,
    actor_id: str,
    case_name: str,
    case_content: str,
    report_id: str | None,
    result_out: dict[str, Any],
    activity_builder: Callable[[str], tuple[str, str]],
    queue_for_delivery: bool,
) -> py_trees.behaviour.Behaviour:
    """Return trigger-side BT for case creation + outbound Create activity.

    ``queue_for_delivery`` is ``False`` when the activity names no recipient:
    the case and its ``Create`` are still built, but nothing is queued, since
    the outbox refuses an activity whose ``to:`` names no one (OX-08-001).

    The creating actor (*actor_id*) is the case's CASE_OWNER and its
    CASE_MANAGER (CM-02-015), so it commits the case's creation entries:
    the genesis ``create_case`` entry, then one entry for each record the
    tree wrote (CLP-07-013).  ``CommitNativeLedgerEntriesNode`` is the same
    node the case-proposal tree composes, so a case created either way is
    committed as the same entry sequence.  It runs after the ``Create`` is
    queued, as on the proposal path (CP-09-009): the entries record a case
    whose creation was sent (ADR-0119).  A genesis entry that fails to
    commit withdraws the ``Create`` from the outbox and the case with it
    (``WithdrawUncommittedCaseNode``), as does a ``Create`` the outbox
    could not take; a later entry that fails stops the
    tree with the ``Create`` queued and the genesis recorded.  The ports
    those commits need are checked first, so a composition fault refuses
    before the case is written.
    """
    children: list[py_trees.behaviour.Behaviour] = [
        RequireWireRenderPortNode(),
        RequireSyncPortNode(),
        _CreateCaseRecordNode(
            case_name=case_name,
            case_content=case_content,
            report_id=report_id,
            result_out=result_out,
        ),
        _RegisterCreatorParticipantNode(),
        _BuildCreateCaseActivityNode(
            activity_builder=activity_builder,
            result_out=result_out,
        ),
    ]
    outbox_step = UpdateActorOutbox() if queue_for_delivery else None
    commit = CommitNativeLedgerEntriesNode(
        owner_uri=actor_id, report_id=report_id
    )
    # The outbox write sits under the withdraw too: a Create that could not
    # be queued leaves a case nothing committed or sent, which is withdrawn.
    send_then_commit = py_trees.composites.Sequence(
        name="QueueThenCommitCase",
        memory=False,
        children=[*([outbox_step] if outbox_step else []), commit],
    )
    children.append(
        py_trees.composites.Selector(
            name="CommitOrWithdrawCase",
            memory=False,
            children=[
                send_then_commit,
                WithdrawUncommittedCaseNode(
                    commit=commit, outbox_step=outbox_step
                ),
            ],
        )
    )
    return py_trees.composites.Sequence(
        name="CreateCaseTriggerBT",
        memory=False,
        children=children,
    )
