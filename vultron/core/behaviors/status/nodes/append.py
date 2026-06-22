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

"""Append-participant-status leaf nodes for DEMOMA-07-003 step 2.

Contains the five leaf nodes that implement the append sequence:
load participant, check idempotency, resolve status object, validate RM
transition, and append + save.
"""

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.models.protocols import (
    PersistableModel,
    is_participant_model,
)
from vultron.core.states.rm import (
    RM,
    is_monotonic_rm_forward,
    is_valid_rm_transition,
)
from vultron.core.use_cases._helpers import _as_id

logger = logging.getLogger(__name__)


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
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(
            key="append_status_participant",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        participant = self.blackboard.get("append_status_participant")
        if participant is None:
            return Status.FAILURE

        existing_ids = [_as_id(s) for s in participant.participant_statuses]
        if self.status_id in existing_ids:
            logging.getLogger(self.__class__.__module__).info(
                "SkipIfIdempotentNode: status '%s' already on participant"
                " '%s' — idempotent, skipping (SUCCESS)",
                self.status_id,
                self.participant_id,
            )
            return Status.SUCCESS
        return Status.FAILURE


class LoadParticipantNode(DataLayerAction):
    """Load the CaseParticipant from DataLayer to blackboard.

    Reads the participant by ID and writes it to the blackboard under the key
    ``append_status_participant``.

    Returns SUCCESS if the participant is found and is a valid participant model.
    Returns FAILURE if participant not found or is not a participant model.
    """

    def __init__(self, participant_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.participant_id = participant_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="append_status_participant",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        participant = self.datalayer.read(self.participant_id)
        if not is_participant_model(participant):
            self.feedback_message = (
                f"Participant '{self.participant_id}' not found"
            )
            self.logger.warning(
                "LoadParticipantNode: %s", self.feedback_message
            )
            return Status.FAILURE

        self.logger.debug(
            "LoadParticipantNode: loaded participant '%s'",
            self.participant_id,
        )
        self.blackboard.set(
            "append_status_participant", participant, overwrite=True
        )
        return Status.SUCCESS


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

        existing_ids = [_as_id(s) for s in participant.participant_statuses]
        if self.status_id in existing_ids:
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


class ResolveAndPersistStatusObjectNode(DataLayerAction):
    """Resolve the status object by ID, persisting fallback if needed.

    Tries the DataLayer first; if not found, uses ``status_obj_fallback``,
    saves it, then re-reads the canonical wire-format record.

    Validates that the resolved object is a ParticipantStatus (has rm_state and
    vfd_state attributes).

    Writes the resolved status object to the blackboard under the key
    ``append_status_status_obj``.

    Returns SUCCESS if status is resolved and valid.
    Returns FAILURE if status cannot be resolved or is not a ParticipantStatus.
    """

    def __init__(
        self,
        status_id: str,
        status_obj_fallback: PersistableModel | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_id = status_id
        self.status_obj_fallback = status_obj_fallback

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="append_status_status_obj",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        status_obj = self.datalayer.read(self.status_id)
        if not hasattr(status_obj, "id_"):
            status_obj = self.status_obj_fallback
            if status_obj is not None:
                self.datalayer.save(status_obj)
                status_obj = self.datalayer.read(self.status_id) or status_obj

        if status_obj is None or not hasattr(status_obj, "id_"):
            self.feedback_message = f"Status '{self.status_id}' not found"
            self.logger.warning(
                "ResolveAndPersistStatusObjectNode: %s",
                self.feedback_message,
            )
            return Status.FAILURE

        if not hasattr(status_obj, "rm_state") or not hasattr(
            status_obj, "vfd_state"
        ):
            self.feedback_message = (
                f"Object '{self.status_id}' is not a ParticipantStatus"
            )
            self.logger.warning(
                "ResolveAndPersistStatusObjectNode: %s",
                self.feedback_message,
            )
            return Status.FAILURE

        self.logger.debug(
            "ResolveAndPersistStatusObjectNode: resolved status '%s'",
            self.status_id,
        )
        self.blackboard.set(
            "append_status_status_obj", status_obj, overwrite=True
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

        new_rm_state = getattr(status_obj, "rm_state", None)
        current_status = getattr(participant, "participant_status", None)

        if new_rm_state is None or current_status is None:
            self.logger.debug(
                "ValidateRMTransitionNode: no current status or new RM state,"
                " skipping validation"
            )
            return Status.SUCCESS

        current_rm = current_status.rm_state
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


class AppendStatusAndSaveParticipantNode(DataLayerAction):
    """Append the status object to the participant and save.

    Appends the resolved status object (from blackboard) to the participant's
    status list and saves the participant to the DataLayer.

    Returns SUCCESS on successful append and save.
    Returns FAILURE if participant or status not on blackboard.
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
        self.blackboard.register_key(
            key="append_status_status_obj",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        participant = self.blackboard.get("append_status_participant")
        status_obj = self.blackboard.get("append_status_status_obj")

        if participant is None or status_obj is None:
            self.feedback_message = "Participant or status not on blackboard"
            self.logger.warning(
                "AppendStatusAndSaveParticipantNode: %s",
                self.feedback_message,
            )
            return Status.FAILURE

        from vultron.core.models.protocols import ParticipantStatusModel

        participant.participant_statuses.append(
            cast(ParticipantStatusModel, status_obj)
        )
        self.datalayer.save(participant)
        self.logger.info(
            "AppendStatusAndSaveParticipantNode: added status '%s' to"
            " participant '%s' (DEMOMA-07-003 step 2)",
            self.status_id,
            self.participant_id,
        )
        return Status.SUCCESS


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
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        participant = self.datalayer.read(self.participant_id)
        if not is_participant_model(participant):
            self.logger.debug(
                "%s: participant '%s' not found — allowing (no terminal check)",
                self.name,
                self.participant_id,
            )
            return Status.SUCCESS

        current_status = getattr(participant, "participant_status", None)
        if current_status is None:
            return Status.SUCCESS

        current_rm = getattr(current_status, "rm_state", None)
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
