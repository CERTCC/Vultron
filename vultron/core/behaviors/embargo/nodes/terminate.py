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

"""Embargo termination ask: the emit node and its pending-ask guard.

A participant that does not hold ``CVDRole.CASE_MANAGER`` asks the manager to
end the embargo and records the ask in its pending-assertion store, keyed by
the embargo it ends (EP-09-008, SYNC-11-002).  A repeat inside the window is
suppressed by :class:`TeardownAskPendingNode`; the manager's announced commit
of the ask clears it (SYNC-11-003).  BTND-07-005.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.emit import _SendEmbargoActivityBase
from vultron.core.behaviors.embargo.nodes.manager_commit import (
    EMBARGO_TEARDOWN_EVENT_TYPE,
)
from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.models.pending_assertion import (
    record_pending_assertion,
    suppressed_repeat_reason,
)
from vultron.errors import VultronWiringError


class TeardownAskPendingNode(DataLayerConditionWithPorts):
    """SUCCESS when this actor already asked for this embargo's teardown.

    The guard ahead of :class:`SendTerminateEmbargoActivityNode` in the
    received-side ask (``terminate_embargo_bt`` with no activity builder):
    a P/X/A signal repeated inside the pending window — the same status
    arriving twice, or a second threat dimension — would otherwise queue a
    second ``Remove(EmbargoEvent)`` for an embargo the CASE_MANAGER has not
    answered yet (SYNC-11-002).  The trigger path makes the same check in
    ``SvcEmbargoTriggerBase._suppressed_duplicate()``; both go through
    ``suppressed_repeat_reason()``, so an ask from either path suppresses a
    repeat from the other.

    FAILURE (ask) when nothing is pending, the entry was cleared by the
    manager's announced commit (SYNC-11-003), or it timed out (SYNC-11-005).
    Raises :class:`VultronWiringError` when the executing actor is unknown:
    a FAILURE there would read as "not pending" and send the ask anyway.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "embargo_id": PortInformation(data_type=str, required=True),
    }

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"embargo_id": "/embargo_id"}

    def initialise(self) -> None:
        super().initialise()
        self.embargo_id: str = self.get_input("embargo_id")

    def update(self) -> Status:
        if not self.actor_id:
            raise VultronWiringError(
                f"{self.name}: no executing actor to look up a pending"
                f" teardown ask on case '{self._case_id}'"
            )
        reason = suppressed_repeat_reason(
            self.actor_id,
            self._case_id,
            EMBARGO_TEARDOWN_EVENT_TYPE,
            self.embargo_id,
        )
        if reason is None:
            return Status.FAILURE
        self.feedback_message = reason
        self.logger.info("%s: %s", self.name, reason)
        return Status.SUCCESS


class SendTerminateEmbargoActivityNode(_SendEmbargoActivityBase):
    """Ask the CASE_MANAGER to end the embargo: queue ``Remove(EmbargoEvent)``.

    The non-manager arm of ``terminate_embargo_bt`` on the cascades, where no
    use case builds the activity.  Reads ``embargo_id`` and
    ``case_manager_id`` from the blackboard, builds the activity through
    ``trigger_activity_factory`` addressed to the manager alone (PCR-08-001),
    and once it is queued records the ask in this actor's pending-assertion
    store, keyed by the embargo it ends (EP-09-008, SYNC-11-002).

    The CASE_MANAGER never runs this node: its arm commits and announces the
    teardown itself (``CommitEmbargoTeardownNode``, EMB-19-001), and it keeps
    no pending assertions (SYNC-11-004).  An executing actor that *is* the
    manager is a composition fault and raises :class:`VultronWiringError`
    rather than mailing the manager an ask from itself.

    Returns FAILURE (BT-14-001) when the factory is unavailable, a required
    blackboard key is missing, the outbox write fails, or dispatch raises an
    exception.  Returns SUCCESS when the activity is created, queued and
    recorded.

    Raises :class:`VultronWiringError` when the executing actor is the
    manager; the bridge reports it by type.  A failure to record the queued
    ask also escapes ``update()`` rather than reporting a success the next
    repeat would not be suppressed by (BT-HELPER-01).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(case_id=case_id, name=name)

    INPUT_PORTS: dict[str, PortInformation] = {
        **_SendEmbargoActivityBase.INPUT_PORTS,
        "embargo_id": PortInformation(data_type=str, required=True),
        "case_manager_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "embargo_id": "/embargo_id",
            "case_manager_id": "/case_manager_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.embargo_id: str = self.get_input("embargo_id")
        self.case_manager_id: str = self.get_input("case_manager_id")

    def _on_factory_unavailable(self) -> Status:
        self.feedback_message = (
            "trigger_activity_factory not available"
            " — broadcast FAILURE (BT-14-001)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _resolve_embargo_and_manager(self) -> "tuple[str, str] | Status":
        if self.actor_id == self.case_manager_id:
            raise VultronWiringError(
                f"{self.name}: the CASE_MANAGER '{self.actor_id}' reached the"
                f" teardown ask on case '{self._case_id}' — its arm commits"
                " the teardown itself (EP-09-008, EMB-19-001)"
            )
        return self.embargo_id, self.case_manager_id

    def _call_factory(
        self, actor_id: str, embargo_id: str, case_manager_id: str
    ) -> tuple[str, object]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.terminate_embargo(
            embargo_id=embargo_id,
            case_id=self._case_id,
            actor=actor_id,
            to=[case_manager_id],
        )

    def _on_queued(self, activity_id: str) -> None:
        assert self.actor_id is not None
        record_pending_assertion(
            self.actor_id,
            self._case_id,
            EMBARGO_TEARDOWN_EVENT_TYPE,
            activity_id,
            subject_id=self.embargo_id,
        )

    def _on_outbox_write_failure(
        self, activity_id: str, exc: Exception
    ) -> Status:
        self.feedback_message = (
            f"Outbox write failed for Terminate(EmbargoEvent)"
            f" '{activity_id}': {exc}"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


def ask_case_manager_to_terminate_once(
    case_id: str,
) -> py_trees.behaviour.Behaviour:
    """The cascades' ask: queue ``Remove(EmbargoEvent)`` unless already asked.

    The non-manager arm of ``terminate_embargo_bt`` when no trigger use case
    builds the activity (the CS.P/X/A cascade in
    ``ThreatTerminationBranchNode``).  There is no use case to record the ask
    or suppress a repeat, so this subtree does both (EP-09-008, SYNC-11-002):
    SUCCESS without sending when the ask is still pending, else the send
    node's result, whose FAILURE still fails the tree (BT-14-001).
    """
    return py_trees.composites.Selector(
        name="AskCaseManagerToTerminateOnce",
        memory=False,
        children=[
            TeardownAskPendingNode(case_id=case_id),
            SendTerminateEmbargoActivityNode(case_id=case_id),
        ],
    )
