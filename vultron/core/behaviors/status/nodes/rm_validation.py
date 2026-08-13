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

Both nodes here adjudicate the ``rm`` dimension *alone* and refuse the whole
snapshot when it is unacceptable.  That is correct for the standalone
``append_participant_status_tree``, where the caller has already decided which
status to append, but it is the wrong shape for a receive-side seam — see
:mod:`vultron.core.behaviors.status.nodes.dimension_filter` and ADR-0061
(RSH-05, ISSUE-2235).
"""

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerCondition, read_rm_states
from vultron.core.behaviors.status.nodes.dimension_filter import (
    BB_DIMENSION_FILTER,
    resolve_dimension_filter,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.rm import (
    RM,
    is_monotonic_rm_forward,
    is_valid_rm_transition,
)

logger = logging.getLogger(__name__)


class ValidateRMTransitionNode(DataLayerCondition):
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

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="append_status_participant",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="append_status_status_obj",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key=BB_DIMENSION_FILTER,
            access=py_trees.common.Access.READ,
        )

    def _rm_was_carried_forward(
        self, current_rm: RM, new_rm_state: RM
    ) -> bool:
        """Return True if the filter node refused ``rm`` and carried *current*.

        Only a filtered status that actually restates the current RM value is
        honoured; anything else falls through to the normal checks.
        """
        if not self.status_id:
            return False
        filtered = resolve_dimension_filter(self.blackboard, self.status_id)
        if filtered is None or "rm" not in filtered["refused"]:
            return False
        return current_rm == new_rm_state

    def update(self) -> Status:
        participant = self.blackboard.get("append_status_participant")
        status_obj = self.blackboard.get("append_status_status_obj")

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
        if self._rm_was_carried_forward(current_rm, new_rm_state):
            self.logger.debug(
                "ValidateRMTransitionNode: rm was refused upstream and"
                " carried forward as %s — accepting (RSH-05)",
                current_rm,
            )
            return Status.SUCCESS

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
            self.logger.info(
                "ValidateRMTransitionNode: non-adjacent forward RM"
                " transition %s → %s for participant '%s';"
                " accepting sender-authoritative state",
                current_rm,
                new_rm_state,
                self.participant_id,
            )
            return Status.SUCCESS

        self.feedback_message = (
            f"Backwards RM transition {current_rm} → {new_rm_state}"
            f" for participant '{self.participant_id}'"
        )
        self.logger.warning(
            "ValidateRMTransitionNode: %s — rejecting",
            self.feedback_message,
        )
        return Status.FAILURE


class CheckParticipantRMNotClosedNode(DataLayerCondition):
    """Pre-flight guard: FAILURE when participant is in RM.CLOSED with no prior
    status match.

    .. deprecated:: RSH-05

        Superseded by
        :class:`~vultron.core.behaviors.status.nodes.dimension_filter.FilterParticipantStatusDimensionsNode`,
        which subsumes this terminal-``RM.CLOSED`` check and no longer discards
        the other dimensions of the snapshot along with ``rm``.  Do not wire
        this node back into ``add_participant_status_tree`` — an all-or-nothing
        RM guard there is exactly the defect in ISSUE-2235.  Retained for
        callers that want the narrow check in isolation.

    Rejects CLOSED→CLOSED rewrites before the commit runs (CLP-10-006).

    When ``status_id`` is supplied and the participant is CLOSED, returns
    SUCCESS if ``status_id`` is already in ``participant.participant_statuses``
    (idempotent delivery of a VALID→CLOSED update whose trigger side already
    appended the status).  Returns FAILURE only for genuine CLOSED→CLOSED
    rewrite attempts (status not yet in participant's list).

    Returns SUCCESS when the participant has no current status, the current
    RM state is not CLOSED, or the incoming status was already appended.
    """

    def __init__(
        self,
        participant_id: str,
        status_id: str = "",
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.participant_id = participant_id
        self.status_id = status_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        participant = self.datalayer.read(self.participant_id)
        if not isinstance(participant, CaseParticipant):
            self.logger.debug(
                "%s: participant '%s' not found — allowing (no terminal check)",
                self.name,
                self.participant_id,
            )
            return Status.SUCCESS

        current_status = getattr(participant, "participant_status", None)
        if current_status is None:
            return Status.SUCCESS

        states = read_rm_states(self, current_status)
        if states is None:
            return Status.FAILURE
        (current_rm,) = states
        if current_rm != RM.CLOSED:
            return Status.SUCCESS

        # Participant is CLOSED. Allow if the incoming status was already
        # appended by the trigger side (idempotent re-delivery of VALID→CLOSED).
        if self.status_id:
            existing_ids = [
                _as_id(s)
                for s in getattr(participant, "participant_statuses", [])
            ]
            if self.status_id in existing_ids:
                self.logger.debug(
                    "%s: participant '%s' is CLOSED but status '%s' already"
                    " in participant_statuses — allowing idempotent commit",
                    self.name,
                    self.participant_id,
                    self.status_id,
                )
                return Status.SUCCESS

        self.feedback_message = (
            f"Participant '{self.participant_id}' is already in terminal"
            " RM.CLOSED — rejecting status update (DEMOMA-07-003)"
        )
        self.logger.info(
            "%s: %s",
            self.name,
            self.feedback_message,
        )
        return Status.FAILURE
