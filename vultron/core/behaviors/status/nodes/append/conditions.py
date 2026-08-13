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

Contains the four precondition and idempotency-guard nodes:

- :class:`SkipIfIdempotentNode` — Selector-level skip when status is already
  present.
- :class:`CheckStatusNotAlreadyAppendedNode` — Sequence-level guard: halt if
  already appended.
- :class:`ValidateRMTransitionNode` — Reject backwards RM transitions.
- :class:`CheckParticipantRMNotClosedNode` — Pre-flight guard: reject rewrites
  for already-closed participants.
"""

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerCondition
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models._helpers import _as_id
from vultron.core.states.rm import (
    RM,
    is_monotonic_rm_forward,
    is_valid_rm_transition,
)

logger = logging.getLogger(__name__)


def _has_status_in_participant(participant: Any, status_id: str) -> bool:
    """Return True when *status_id* is already in the participant's status list."""
    existing_ids = [_as_id(s) for s in participant.participant_statuses]
    return status_id in existing_ids


class SkipIfIdempotentNode(py_trees.behaviour.Behaviour):
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

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(
            key="append_status_participant",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        participant = self.blackboard.get("append_status_participant")
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


class CheckStatusNotAlreadyAppendedNode(DataLayerCondition):
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

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="append_status_participant",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        participant = self.blackboard.get("append_status_participant")
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


class ValidateRMTransitionNode(DataLayerCondition):
    """Validate RM state transition rules.

    Checks that the new RM state does not violate transition rules:
    - Accepts non-adjacent forward RM jumps (sender is authoritative)
    - Rejects backwards RM transitions

    Returns SUCCESS if the transition is valid or if participant has no current
    status (nothing to validate against).

    Returns FAILURE if a backwards RM transition is detected.
    """

    def __init__(self, participant_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.participant_id = participant_id

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

    def update(self) -> Status:
        participant = self.blackboard.get("append_status_participant")
        status_obj = self.blackboard.get("append_status_status_obj")

        if participant is None or status_obj is None:
            self.feedback_message = "Participant or status not on blackboard"
            self.logger.warning(
                "ValidateRMTransitionNode: %s", self.feedback_message
            )
            return Status.FAILURE

        new_rm_state = (
            status_obj.rm.state if hasattr(status_obj, "rm") else None
        )
        current_status = getattr(participant, "participant_status", None)

        if new_rm_state is None or current_status is None:
            self.logger.debug(
                "ValidateRMTransitionNode: no current status or new RM state,"
                " skipping validation"
            )
            return Status.SUCCESS

        current_rm = current_status.rm.state
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

    Used in ``add_participant_status_tree`` precondition guards to reject
    CLOSED→CLOSED rewrites before the commit runs (CLP-10-006).

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

        current_rm = (
            current_status.rm.state if hasattr(current_status, "rm") else None
        )
        if current_rm != RM.CLOSED:
            return Status.SUCCESS

        # Participant is CLOSED. Allow if the incoming status was already
        # appended by the trigger side (idempotent re-delivery of VALID→CLOSED).
        if self.status_id and _has_status_in_participant(
            participant, self.status_id
        ):
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
