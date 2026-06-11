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

"""Participant status workflow nodes for AddParticipantStatusToParticipant.

Contains the load, idempotency check, status resolution, RM transition
validation, append, public disclosure branch, and auto-close nodes that
implement steps 2–5 of DEMOMA-07-003.
"""

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes import TerminateEmbargoNode
from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.behaviors.status.nodes.broadcast import _find_case_manager_id
from vultron.core.models.protocols import (
    PersistableModel,
    is_case_model,
    is_participant_model,
)
from vultron.core.states.rm import (
    RM,
    is_monotonic_rm_forward,
    is_valid_rm_transition,
)
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases._helpers import _as_id

logger = logging.getLogger(__name__)


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


class _PublicDisclosureSkipConditionNode(DataLayerCondition):
    """Inner guard for :class:`PublicDisclosureBranchNode`.

    Returns SUCCESS (skip teardown) when:
    - The new status is NOT public-aware (CS.P not set), OR
    - DataLayer or case_id is unavailable, OR
    - The sender is not a known case participant, OR
    - The sender does NOT hold the CASE_OWNER role.

    Returns FAILURE (proceed to teardown) when the sender IS a CASE_OWNER
    who has sent a public-aware status update.
    """

    def __init__(
        self,
        status_obj: PersistableModel | None,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_obj = status_obj
        self.sender_actor_id = sender_actor_id
        self.case_id = case_id

    def _public_aware(self) -> bool:
        """Return True if the status signals public awareness (CS.P is set)."""
        from vultron.core.states.cs import CS_pxa

        case_status = getattr(self.status_obj, "case_status", None)
        pxa_state = getattr(case_status, "pxa_state", None)
        if pxa_state is None:
            return False
        try:
            return pxa_state in (
                CS_pxa.Pxa,
                CS_pxa.PxA,
                CS_pxa.PXa,
                CS_pxa.PXA,
            )
        except Exception:
            return False

    def update(self) -> Status:
        if not self._public_aware():
            return Status.SUCCESS

        if self.datalayer is None or not self.case_id:
            return Status.SUCCESS

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            return Status.SUCCESS

        sender_participant_id = case.actor_participant_index.get(
            self.sender_actor_id
        )
        if sender_participant_id is None:
            return Status.SUCCESS

        sender_participant = self.datalayer.read(sender_participant_id)
        roles = getattr(sender_participant, "case_roles", [])
        if CVDRole.CASE_OWNER not in roles:
            return Status.SUCCESS

        # Condition met: sender is CASE_OWNER reporting public awareness.
        return Status.FAILURE


class PublicDisclosureBranchNode(py_trees.composites.Selector):
    """Step 4: Trigger embargo teardown if public disclosure is detected.

    Condition: the new ParticipantStatus has CS.P (public-aware) set AND
    the sender holds the CASE_OWNER role.

    When the condition is met, delegates to :class:`TerminateEmbargoNode`.
    Skips silently if conditions are not met or trigger_activity_factory
    is unavailable.

    Always returns SUCCESS (failure to initiate teardown is not fatal to
    the parent sequence).

    Implemented as a ``py_trees.composites.Selector`` (memory=False):
    - Child 1 ``_PublicDisclosureSkipConditionNode``: SUCCESS → skip teardown.
    - Child 2 ``TerminateEmbargoNode``: always SUCCESS → teardown attempted.

    Per DEMOMA-07-003 step 4.
    """

    def __init__(
        self,
        status_obj: PersistableModel | None,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__, memory=False)
        self.add_children(
            [
                _PublicDisclosureSkipConditionNode(
                    status_obj=status_obj,
                    sender_actor_id=sender_actor_id,
                    case_id=case_id,
                    name="SkipCondition",
                ),
                TerminateEmbargoNode(
                    case_id=case_id,
                    name="TerminateEmbargo",
                ),
            ]
        )


class AutoCloseBranchNode(DataLayerAction):
    """Step 5: Log case auto-close when all participants are RM.CLOSED.

    Checks whether every CVD participant in the case has ``RM.CLOSED``
    as their most recent status.  The CASE_MANAGER (Case Actor) is a
    coordinator role and is excluded from this check.

    Actual case closure is **not** persisted here — this is log-only
    behaviour for the prototype demo.

    Always returns SUCCESS.

    Per DEMOMA-07-003 step 5.
    """

    def __init__(
        self,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def _all_participants_closed(self, case: Any) -> bool:
        """Return True iff every CVD participant has RM.CLOSED."""
        if self.datalayer is None:
            return False

        for p_id in case.actor_participant_index.values():
            p = self.datalayer.read(p_id)
            if p is None:
                return False
            roles = getattr(p, "case_roles", [])
            if CVDRole.CASE_MANAGER in roles:
                continue
            statuses = getattr(p, "participant_statuses", [])
            if not statuses:
                return False
            latest_ref = statuses[-1]
            if isinstance(latest_ref, str):
                ref_id = _as_id(latest_ref)
                if ref_id is None:
                    return False
                latest = self.datalayer.read(ref_id)
            else:
                latest = latest_ref
            if latest is None:
                return False
            rm_state = getattr(latest, "rm_state", None)
            if rm_state is None or rm_state != RM.CLOSED:
                return False
        return True

    def update(self) -> Status:
        if self.datalayer is None or not self.case_id:
            return Status.SUCCESS

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            return Status.SUCCESS

        if not self._all_participants_closed(case):
            return Status.SUCCESS

        case_manager_id = _find_case_manager_id(self.datalayer, case)
        if case_manager_id is None:
            self.logger.warning(
                "AutoCloseBranch: no Case Manager found"
                " — cannot auto-close case '%s'",
                self.case_id,
            )
            return Status.SUCCESS

        self.logger.info(
            "AutoCloseBranch: Case Manager '%s' auto-closing case '%s'"
            " — all participants CLOSED (DEMOMA-07-003 step 5)",
            case_manager_id,
            self.case_id,
        )
        return Status.SUCCESS
