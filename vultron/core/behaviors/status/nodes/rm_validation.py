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

"""RM-transition guards for the append-participant-status path.

``ValidateRMTransitionNode`` adjudicates the ``rm`` dimension alone and is
appropriate for standalone use of ``append_participant_status_tree``.  When
called from ``add_participant_status_tree`` the rm dimension has already been
adjudicated by ``FilterParticipantStatusDimensionsNode`` in
``precondition_guards`` (CLP-10-009, RSH-05), so ``validate_rm=False`` is
passed to skip this node and avoid a redundant post-commit check.
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    PortInformation,
    read_rm_states,
)
from vultron.core.behaviors.status.nodes.dimension_filter import BB_RM_ANOMALY
from vultron.core.states.rm import (
    RM,
    is_monotonic_rm_forward,
    is_valid_rm_transition,
)

logger = logging.getLogger(__name__)


class ValidateRMTransitionNode(DataLayerConditionWithPorts):
    """Validate RM state transition rules.

    Checks that the new RM state does not violate transition rules:
    - Accepts non-adjacent forward RM jumps (sender is authoritative)
    - Rejects backwards RM transitions

    When
    :class:`~vultron.core.behaviors.status.nodes.dimension_filter.FilterParticipantStatusDimensionsNode`
    has already refused the ``rm`` dimension and carried the participant's
    current value forward, this node accepts that value: the transition was
    adjudicated upstream and re-rejecting it here would abort the Sequence and
    discard the dimensions that *were* accepted (RSH-05, ISSUE-2235).  The
    checks below still apply when the node is used standalone, without the
    filter — which is how ``append_participant_status_tree`` is exercised
    directly.

    Returns SUCCESS if the transition is valid or if participant has no current
    status (nothing to validate against).

    Returns FAILURE if a backwards RM transition is detected.
    """

    def __init__(
        self,
        participant_id: str,
        status_id: str = "",
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.participant_id = participant_id
        self.status_id = status_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["append_status_participant"] = PortInformation(
            data_type=object, required=True
        )
        ports["append_status_status_obj"] = PortInformation(
            data_type=object, required=True
        )
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            BB_RM_ANOMALY: PortInformation(data_type=object, required=False)
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "append_status_participant": "/append_status_participant",
            "append_status_status_obj": "/append_status_status_obj",
            BB_RM_ANOMALY: f"/{BB_RM_ANOMALY}",
        }

    def initialise(self) -> None:
        super().initialise()
        self.append_status_participant = self.get_input(
            "append_status_participant"
        )
        self.append_status_status_obj = self.get_input(
            "append_status_status_obj"
        )

    def update(self) -> Status:
        # Clear on every tick so a previous run's flag never leaks forward.
        self._set_output(BB_RM_ANOMALY, None)

        participant = self.append_status_participant
        status_obj = self.append_status_status_obj

        if participant is None or status_obj is None:
            self.feedback_message = "Participant or status not on blackboard"
            self.logger.warning(
                "ValidateRMTransitionNode: %s", self.feedback_message
            )
            return Status.FAILURE

        current_status = getattr(participant, "participant_status", None)
        if current_status is None:
            self.logger.debug("ValidateRMTransitionNode: no current status")
            return Status.SUCCESS

        states = read_rm_states(self, status_obj, current_status)
        if states is None:
            return Status.FAILURE
        new_rm_state, current_rm = states

        if current_rm == RM.CLOSED:
            self.feedback_message = (
                "Participant is already in terminal RM.CLOSED state"
                f" (received {new_rm_state}) for participant"
                f" '{self.participant_id}'"
            )
            self.logger.info(
                "ValidateRMTransitionNode: %s — rejecting",
                self.feedback_message,
            )
            return Status.FAILURE

        if current_rm == new_rm_state:
            self.logger.debug(
                "ValidateRMTransitionNode: no RM state change (both %s)",
                current_rm,
            )
            return Status.SUCCESS

        if is_valid_rm_transition(current_rm, new_rm_state):
            self.logger.debug(
                "ValidateRMTransitionNode: valid adjacent transition"
                " %s → %s",
                current_rm,
                new_rm_state,
            )
            return Status.SUCCESS

        if is_monotonic_rm_forward(current_rm, new_rm_state):
            # RSH-06-001: accept; RSH-06-003: must not be silent.
            self.logger.warning(
                "ValidateRMTransitionNode: non-adjacent forward RM"
                " transition %s → %s for participant '%s';"
                " accepting sender-authoritative state (RSH-06-001)",
                current_rm,
                new_rm_state,
                self.participant_id,
            )
            self._set_output(
                BB_RM_ANOMALY,
                {
                    "anomaly_type": "gap",
                    "from_rm": current_rm,
                    "to_rm": new_rm_state,
                },
            )
            return Status.SUCCESS

        # RSH-06-002: backward regression — refuse; RSH-06-003: not silent.
        self.feedback_message = (
            f"Backwards RM transition {current_rm} → {new_rm_state}"
            f" for participant '{self.participant_id}'"
        )
        self.logger.warning(
            "ValidateRMTransitionNode: %s — rejecting (RSH-06-002)",
            self.feedback_message,
        )
        self._set_output(
            BB_RM_ANOMALY,
            {
                "anomaly_type": "regression",
                "from_rm": current_rm,
                "to_rm": new_rm_state,
            },
        )
        return Status.FAILURE
