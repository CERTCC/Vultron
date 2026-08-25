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

"""RM transition anomaly notification node.

Extracted from ``lifecycle.py`` to keep that module under the 500-line
BTND-07-004 limit.  Re-exported from ``nodes/__init__.py`` so existing import
paths continue to work.

Per specs/received-status-handling.yaml RSH-06-004, RSH-06-005.
"""

import logging
from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.behaviors.status.nodes.dimension_filter import BB_RM_ANOMALY

logger = logging.getLogger(__name__)


class EmitRMGapNoteNode(DataLayerActionWithPorts):
    """Emit ``Add(Note, VulnerabilityCase)`` when an RM transition anomaly is detected.

    Reads the ``rm_transition_anomaly`` blackboard key written by
    :class:`~vultron.core.behaviors.status.nodes.dimension_filter.FilterParticipantStatusDimensionsNode`
    (non-adjacent forward jump) or
    :class:`~vultron.core.behaviors.status.nodes.rm_validation.ValidateRMTransitionNode`
    (backward regression on the standalone path).  When the key is ``None``
    (no anomaly), returns SUCCESS without doing anything.

    When an anomaly is present, creates a note describing the anomaly and
    queues an ``Add(Note, VulnerabilityCase)`` addressed to the sender.
    Returns SUCCESS in all cases — note emission is SHOULD-level (RSH-06-004);
    failures degrade gracefully so the enclosing Sequence is not aborted.

    Per specs/received-status-handling.yaml RSH-06-004, RSH-06-005.
    """

    def __init__(
        self,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.sender_actor_id = sender_actor_id
        self.case_id = case_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports[BB_RM_ANOMALY] = PortInformation(
            data_type=object, required=False
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {BB_RM_ANOMALY: f"/{BB_RM_ANOMALY}"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self.rm_anomaly = self.get_input(BB_RM_ANOMALY)
        except (NoDataAvailable, NotImplementedError):
            self.rm_anomaly = None

    def update(self) -> Status:
        if not self.case_id:
            return Status.SUCCESS

        anomaly = self.rm_anomaly
        if anomaly is None:
            return Status.SUCCESS

        if self._require_datalayer_and_actor() is not None:
            self.logger.warning(
                "EmitRMGapNoteNode: no datalayer/actor — cannot emit note"
                " for RM anomaly in case '%s'",
                self.case_id,
            )
            return Status.SUCCESS

        if self.trigger_activity_factory is None:
            self.logger.warning(
                "EmitRMGapNoteNode: no TriggerActivityPort — cannot emit"
                " Add(Note,Case) for RM anomaly in case '%s'",
                self.case_id,
            )
            return Status.SUCCESS

        anomaly_type = anomaly.get("anomaly_type", "unknown")
        from_rm = anomaly.get("from_rm", "?")
        to_rm = anomaly.get("to_rm", "?")

        if anomaly_type == "gap":
            note_name = f"RM state gap reported by {self.sender_actor_id}"
            note_content = (
                f"Actor '{self.sender_actor_id}' reported a non-adjacent forward"
                f" RM state jump from {from_rm} to {to_rm}."
                f" Intermediate transitions were not reported."
                f" Please clarify the path taken between these states (RSH-06-001)."
            )
        else:
            note_name = (
                f"RM state regression reported by {self.sender_actor_id}"
            )
            note_content = (
                f"Actor '{self.sender_actor_id}' reported a backward RM"
                f" state transition from {from_rm} to {to_rm}."
                f" RM is monotonic; this transition was refused (RSH-06-002)."
                f" Please clarify or resync your RM state."
            )

        assert self.datalayer is not None
        assert self.actor_id is not None
        assert self.trigger_activity_factory is not None
        try:
            note_id, _ = self.trigger_activity_factory.create_note(
                name=note_name,
                content=note_content,
                context_id=self.case_id,
                attributed_to=self.actor_id,
            )
            activity_id, _ = self.trigger_activity_factory.add_note_to_case(
                note_id=note_id,
                case_id=self.case_id,
                actor=self.actor_id,
                to=[self.sender_actor_id],
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            self.logger.info(
                "EmitRMGapNoteNode: queued Add(Note,Case) '%s' for RM %s"
                " anomaly (%s → %s) in case '%s' (RSH-06-004)",
                activity_id,
                anomaly_type,
                from_rm,
                to_rm,
                self.case_id,
            )
        except Exception as e:
            self.logger.warning(
                "EmitRMGapNoteNode: failed to emit note for RM anomaly"
                " in case '%s': %s",
                self.case_id,
                e,
            )

        return Status.SUCCESS
