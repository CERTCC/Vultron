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

"""Condition (guard) nodes for the append-participant-status workflow.

Contains the two idempotency-guard nodes used directly in the append sequence:

- :class:`SkipIfIdempotentNode` — Selector-level skip when status is already
  present.
- :class:`CheckStatusNotAlreadyAppendedNode` — Sequence-level guard: halt if
  already appended.

RM-transition guards live in
:mod:`vultron.core.behaviors.status.nodes.rm_validation` (BTND-07-004) and are
re-exported here for backward-compatibility.
"""

import logging
from typing import Any

from py_trees.common import Status
from py_trees.ports import BehaviourWithPorts, NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models._helpers import _as_id
from vultron.core.behaviors.status.nodes.rm_validation import (
    CheckParticipantRMNotClosedNode,
    ValidateRMTransitionNode,
)

logger = logging.getLogger(__name__)

__all__ = [
    "SkipIfIdempotentNode",
    "CheckStatusNotAlreadyAppendedNode",
    "ValidateRMTransitionNode",
    "CheckParticipantRMNotClosedNode",
]


def _has_status_in_participant(participant: Any, status_id: str) -> bool:
    """Return True when *status_id* is already in the participant's status list."""
    existing_ids = [_as_id(s) for s in participant.participant_statuses]
    return status_id in existing_ids


class SkipIfIdempotentNode(BehaviourWithPorts):
    """Idempotency guard for the append-participant-status Selector.

    Returns SUCCESS when *status_id* is already present in the participant's
    status list — causing the parent Selector to short-circuit and skip the
    append subtree. Returns FAILURE when the status is not yet appended,
    allowing the parent Selector to continue to the append subtree.

    This is the inverse of :class:`CheckStatusNotAlreadyAppendedNode`: that
    node is used to halt a Sequence on duplicate; this node is used to skip
    an append Selector on duplicate.

    Per DEMOMA-07-003 step 2 idempotency requirement.
    """

    def __init__(
        self,
        status_id: str,
        participant_id: str,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_id = status_id
        self.participant_id = participant_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        return {
            "append_status_participant": PortInformation(
                data_type=object, required=False
            ),
        }

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {}

    def setup(self, **kwargs: Any) -> None:
        self.setup_ports(
            port_remappings={
                "append_status_participant": "/append_status_participant"
            }
        )

    def update(self) -> Status:
        try:
            participant = self.get_input("append_status_participant")
        except (KeyError, NoDataAvailable, NotImplementedError):
            return Status.FAILURE

        if participant is None:
            return Status.FAILURE

        if _has_status_in_participant(participant, self.status_id):
            logging.getLogger(self.__class__.__module__).info(
                "SkipIfIdempotentNode: status '%s' already on participant"
                " '%s' — idempotent, skipping (SUCCESS)",
                self.status_id,
                self.participant_id,
            )
            return Status.SUCCESS
        return Status.FAILURE


class CheckStatusNotAlreadyAppendedNode(DataLayerConditionWithPorts):
    """Check idempotency: is the status already appended to the participant?

    Returns SUCCESS if the status is NOT already on the participant
    (i.e., it's safe to append). Returns SUCCESS if the participant has no
    statuses yet.

    Returns FAILURE if the status ID already exists in the participant's
    status list, indicating the append would be redundant.
    """

    def __init__(
        self, status_id: str, participant_id: str, name: str | None = None
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_id = status_id
        self.participant_id = participant_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["append_status_participant"] = PortInformation(
            data_type=object, required=False
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"append_status_participant": "/append_status_participant"}

    def initialise(self) -> None:
        super().initialise()
        self._participant = None
        try:
            self._participant = self.get_input("append_status_participant")
        except (NoDataAvailable, NotImplementedError):
            self._participant = None

    def update(self) -> Status:
        participant = self._participant
        if participant is None:
            self.feedback_message = "Participant not on blackboard"
            self.logger.warning(
                "CheckStatusNotAlreadyAppendedNode: %s",
                self.feedback_message,
            )
            return Status.FAILURE

        if _has_status_in_participant(participant, self.status_id):
            self.logger.info(
                "CheckStatusNotAlreadyAppendedNode: status '%s' already"
                " on participant '%s' — idempotent, skipping",
                self.status_id,
                self.participant_id,
            )
            return Status.FAILURE

        self.logger.debug(
            "CheckStatusNotAlreadyAppendedNode: status '%s' not yet appended",
            self.status_id,
        )
        return Status.SUCCESS
