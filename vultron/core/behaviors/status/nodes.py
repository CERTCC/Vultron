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

"""
BT nodes for status-related workflows.

Contains nodes for two workflows:

AddParticipantStatusToParticipant (DEMOMA-07-003):
  1. Verify the activity actor is a known case participant.
  2. Append the ParticipantStatus to the CaseParticipant record.
  3. Announce the update to all other case participants.
  4. If CS.P is newly set by the Case Owner, trigger embargo teardown.
  5. If all participants are RM.CLOSED, close the case automatically
     (log-only for prototype).

AddCaseStatusToCase (issue #758):
  1. Check idempotency: CaseStatus not yet in case.case_statuses.
  2. Validate EM/PXA state transitions.
  3. Append CaseStatus to the VulnerabilityCase record.

Per specs/multi-actor-demo.yaml DEMOMA-07-003,
    specs/behavior-tree-integration.yaml BT-06-001.
"""

import logging
from typing import TYPE_CHECKING, Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes import TerminateEmbargoNode
from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.models.protocols import (
    PersistableModel,
    is_case_model,
    is_participant_model,
)
from vultron.core.states.cs import is_valid_pxa_transition
from vultron.core.states.em import is_valid_em_transition
from vultron.core.states.rm import (
    RM,
    is_monotonic_rm_forward,
    is_valid_rm_transition,
)
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases._helpers import _as_id

# Stable sentinel used as feedback_message when a CaseStatus duplicate is
# detected.  The use case imports this constant to distinguish idempotent
# no-ops (log at INFO) from real failures (log at WARNING).
CASE_STATUS_ALREADY_PRESENT = "case_status_already_present"

if TYPE_CHECKING:
    from vultron.core.ports.case_persistence import CasePersistence

logger = logging.getLogger(__name__)


def _find_case_manager_id(dl: "CasePersistence", case: Any) -> str | None:
    """Return the attributed_to actor ID for the CASE_MANAGER participant."""
    for p_id in case.actor_participant_index.values():
        p = dl.read(p_id)
        if p is None:
            continue
        roles = getattr(p, "case_roles", [])
        if CVDRole.CASE_MANAGER in roles:
            attr = getattr(p, "attributed_to", None)
            if attr:
                return str(attr)
    return None


class VerifySenderIsParticipantNode(DataLayerCondition):
    """Step 1: Verify the activity actor is a known case participant.

    Returns SUCCESS if the actor is registered in
    ``case.actor_participant_index``.  Returns FAILURE otherwise, halting
    the parent Sequence.

    If *case_id* is ``None`` the node falls back to a DataLayer lookup of
    *status_id* to derive the case context.

    Per DEMOMA-07-003 step 1.
    """

    def __init__(
        self,
        status_id: str,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_id = status_id
        self.sender_actor_id = sender_actor_id
        self.case_id = case_id

    def _resolve_case_id(self) -> str | None:
        if self.case_id:
            return self.case_id
        assert self.datalayer is not None
        status_raw = self.datalayer.read(self.status_id)
        if status_raw is None:
            return None
        context = getattr(status_raw, "context", None)
        return str(context) if context else None

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case_id = self._resolve_case_id()
        if case_id is None:
            self.feedback_message = (
                f"Cannot determine case_id for status '{self.status_id}'"
            )
            self.logger.warning(
                "VerifySenderIsParticipant: %s", self.feedback_message
            )
            return Status.FAILURE

        case = self.datalayer.read(case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{case_id}' not found"
            self.logger.warning(
                "VerifySenderIsParticipant: %s", self.feedback_message
            )
            return Status.FAILURE

        if self.sender_actor_id not in case.actor_participant_index:
            self.feedback_message = (
                f"Actor '{self.sender_actor_id}' is not a known participant"
                f" of case '{case_id}'"
            )
            self.logger.warning(
                "VerifySenderIsParticipant: %s (DEMOMA-07-003 step 1)",
                self.feedback_message,
            )
            return Status.FAILURE

        self.logger.debug(
            "VerifySenderIsParticipant: actor '%s' is known in case '%s'"
            " (DEMOMA-07-003 step 1)",
            self.sender_actor_id,
            case_id,
        )
        return Status.SUCCESS


class AppendParticipantStatusNode(DataLayerAction):
    """Step 2: Append ParticipantStatus to the CaseParticipant record.

    Validates any RM state transition before appending:
    - Non-adjacent forward RM jumps are accepted (sender is authoritative
      about their own state).
    - Backwards RM transitions are rejected.

    Returns SUCCESS on append (or if status already present — idempotent).
    Returns FAILURE if participant or status cannot be resolved, or if the
    RM transition is invalid.

    Per DEMOMA-07-003 step 2.
    """

    def __init__(
        self,
        status_id: str,
        participant_id: str,
        status_obj_fallback: PersistableModel | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_id = status_id
        self.participant_id = participant_id
        self.status_obj_fallback = status_obj_fallback

    def _resolve_status(self) -> "PersistableModel | None":
        """Resolve the status object by ID, persisting the fallback when needed.

        Tries the DataLayer first; if not found, uses ``status_obj_fallback``,
        saves it, then re-reads the canonical wire-format record.  Returns
        ``None`` when neither source can provide the status.
        """
        dl = self.datalayer
        assert dl is not None  # checked by caller
        status_obj = dl.read(self.status_id)
        if not hasattr(status_obj, "id_"):
            status_obj = self.status_obj_fallback
            if status_obj is not None:
                dl.save(status_obj)
                # Re-read so we get the canonical wire-format object
                # (correct type_ enum) rather than the domain fallback.
                status_obj = dl.read(self.status_id) or status_obj
        return status_obj if hasattr(status_obj, "id_") else None

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
                "AppendParticipantStatus: %s", self.feedback_message
            )
            return Status.FAILURE

        existing_ids = [_as_id(s) for s in participant.participant_statuses]
        if self.status_id in existing_ids:
            self.logger.info(
                "AppendParticipantStatus: status '%s' already on participant"
                " '%s' — skipping (idempotent)",
                self.status_id,
                self.participant_id,
            )
            return Status.SUCCESS

        status_obj = self._resolve_status()
        if status_obj is None:
            self.feedback_message = f"Status '{self.status_id}' not found"
            self.logger.warning(
                "AppendParticipantStatus: %s", self.feedback_message
            )
            return Status.FAILURE
        if not hasattr(status_obj, "rm_state") or not hasattr(
            status_obj, "vfd_state"
        ):
            self.feedback_message = (
                f"Object '{self.status_id}' is not a ParticipantStatus"
            )
            self.logger.warning(
                "AppendParticipantStatus: %s", self.feedback_message
            )
            return Status.FAILURE

        # Validate RM state transition
        new_rm_state = getattr(status_obj, "rm_state", None)
        current_status = getattr(participant, "participant_status", None)
        if new_rm_state is not None and current_status is not None:
            current_rm = current_status.rm_state
            if current_rm != new_rm_state and not is_valid_rm_transition(
                current_rm, new_rm_state
            ):
                if is_monotonic_rm_forward(current_rm, new_rm_state):
                    self.logger.info(
                        "AppendParticipantStatus: non-adjacent forward RM"
                        " transition %s → %s for participant '%s';"
                        " accepting sender-authoritative state",
                        current_rm,
                        new_rm_state,
                        self.participant_id,
                    )
                else:
                    self.feedback_message = (
                        f"Backwards RM transition {current_rm} → {new_rm_state}"
                        f" for participant '{self.participant_id}'"
                    )
                    self.logger.warning(
                        "AppendParticipantStatus: %s — rejecting",
                        self.feedback_message,
                    )
                    return Status.FAILURE

        from vultron.core.models.protocols import ParticipantStatusModel

        participant.participant_statuses.append(
            cast(ParticipantStatusModel, status_obj)
        )
        self.datalayer.save(participant)
        self.logger.info(
            "AppendParticipantStatus: added status '%s' to participant '%s'"
            " (DEMOMA-07-003 step 2)",
            self.status_id,
            self.participant_id,
        )
        return Status.SUCCESS


class BroadcastStatusToPeersNode(DataLayerAction):
    """Step 3: Broadcast Add(ParticipantStatus, CaseParticipant) to peers.

    The current actor re-sends the status update to all other participants,
    excluding the original sender, itself, and the Case Manager. Skips
    silently when no ``trigger_activity_factory`` is available or when there
    are no eligible recipients.

    Always returns SUCCESS (failure to broadcast is not fatal).

    Per DEMOMA-07-003 step 3.
    """

    def __init__(
        self,
        status_id: str,
        participant_id: str,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_id = status_id
        self.participant_id = participant_id
        self.sender_actor_id = sender_actor_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.trigger_activity_factory is None:
            self.logger.debug(
                "BroadcastStatusToPeers: no trigger_activity_factory"
                " — skipping broadcast (DEMOMA-07-003 step 3)"
            )
            return Status.SUCCESS

        if self.datalayer is None or not self.case_id:
            self.logger.debug(
                "BroadcastStatusToPeers: missing datalayer or case_id"
                " — skipping broadcast"
            )
            return Status.SUCCESS

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.logger.debug(
                "BroadcastStatusToPeers: case '%s' not found — skipping",
                self.case_id,
            )
            return Status.SUCCESS

        case_manager_id = _find_case_manager_id(self.datalayer, case)
        if case_manager_id is None:
            self.logger.debug(
                "BroadcastStatusToPeers: no CASE_MANAGER in case '%s'"
                " — skipping broadcast",
                self.case_id,
            )
            return Status.SUCCESS

        recipient_ids = [
            a_id
            for a_id in case.actor_participant_index.keys()
            if (
                a_id != self.sender_actor_id
                and a_id != self.actor_id
                and a_id != case_manager_id
            )
        ]
        if not recipient_ids:
            self.logger.debug(
                "BroadcastStatusToPeers: no eligible recipients in case '%s'"
                " — skipping broadcast",
                self.case_id,
            )
            return Status.SUCCESS

        from vultron.errors import VultronError
        from vultron.core.ports.case_persistence import CaseOutboxPersistence

        try:
            activity_id = self.trigger_activity_factory.add_participant_status_to_participant(
                status_id=self.status_id,
                participant_id=self.participant_id,
                actor=case_manager_id,
                to=recipient_ids,
            )
            case_manager_actor = self.datalayer.read(case_manager_id)
            if case_manager_actor is not None and hasattr(
                case_manager_actor, "outbox"
            ):
                cast(Any, case_manager_actor).outbox.items.append(activity_id)
                self.datalayer.save(case_manager_actor)

            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                case_manager_id, activity_id
            )
            self.logger.info(
                "BroadcastStatusToPeers: Case Manager '%s' broadcast status"
                " '%s' to %d peer(s) (DEMOMA-07-003 step 3)",
                case_manager_id,
                self.status_id,
                len(recipient_ids),
            )
        except VultronError as exc:
            self.logger.warning(
                "BroadcastStatusToPeers: broadcast failed: %s", exc
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


# ---------------------------------------------------------------------------
# AddCaseStatusToCase nodes (issue #758)
# ---------------------------------------------------------------------------


class CheckCaseStatusIdempotencyNode(DataLayerCondition):
    """AC-1: Verify the CaseStatus has not already been added to the case.

    Returns FAILURE with ``feedback_message == CASE_STATUS_ALREADY_PRESENT``
    when *status_id* is already in ``case.case_statuses`` — a benign no-op.

    Returns FAILURE with a distinct message when the case itself is not found.

    Returns SUCCESS when the status is not yet present and the Sequence should
    continue.

    Per issue #758 AC-1.
    """

    def __init__(
        self,
        case_id: str,
        status_id: str,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.status_id = status_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning(
                "CheckCaseStatusIdempotency: %s", self.feedback_message
            )
            return Status.FAILURE

        existing_ids = [_as_id(s) for s in case.case_statuses]
        if self.status_id in existing_ids:
            self.feedback_message = CASE_STATUS_ALREADY_PRESENT
            self.logger.debug(
                "CheckCaseStatusIdempotency: status '%s' already in case '%s'"
                " — skipping (idempotent)",
                self.status_id,
                self.case_id,
            )
            return Status.FAILURE

        return Status.SUCCESS


class ValidateCaseStatusTransitionNode(DataLayerCondition):
    """AC-2: Validate that the new CaseStatus represents a legal state transition.

    Uses ``case.current_status`` as the reference point.  When the case has no
    current status (first status ever), the transition is unconditionally
    allowed.  Otherwise both the EM state and PXA state transitions are
    validated independently.

    Returns SUCCESS when the transition is valid (or there is no prior status).
    Returns FAILURE when an invalid EM or PXA transition is detected.

    Per issue #758 AC-2.
    """

    def __init__(
        self,
        case_id: str,
        status_id: str,
        status_obj_fallback: PersistableModel | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.status_id = status_id
        self.status_obj_fallback = status_obj_fallback

    def _resolve_status(self) -> object | None:
        assert self.datalayer is not None
        status_obj = self.datalayer.read(self.status_id)
        if hasattr(status_obj, "id_"):
            return status_obj
        return self.status_obj_fallback

    def _check_transition(
        self,
        label: str,
        current: object,
        new: object,
        validator: Any,
    ) -> bool:
        if new is None or current == new:
            return True
        if validator(current, new):
            return True
        self.feedback_message = (
            f"Invalid {label} transition {current} → {new}"
            f" for case '{self.case_id}'"
        )
        self.logger.warning(
            "ValidateCaseStatusTransition: %s — rejecting",
            self.feedback_message,
        )
        return False

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning(
                "ValidateCaseStatusTransition: %s", self.feedback_message
            )
            return Status.FAILURE

        current_status = getattr(case, "current_status", None)
        if current_status is None:
            return Status.SUCCESS

        status_obj = self._resolve_status()
        if status_obj is None:
            self.feedback_message = f"Status '{self.status_id}' not found"
            self.logger.warning(
                "ValidateCaseStatusTransition: %s", self.feedback_message
            )
            return Status.FAILURE

        if not self._check_transition(
            "EM",
            current_status.em_state,
            getattr(status_obj, "em_state", None),
            is_valid_em_transition,
        ):
            return Status.FAILURE

        if not self._check_transition(
            "PXA",
            current_status.pxa_state,
            getattr(status_obj, "pxa_state", None),
            is_valid_pxa_transition,
        ):
            return Status.FAILURE

        return Status.SUCCESS


class AppendCaseStatusToCaseNode(DataLayerAction):
    """Append the resolved CaseStatus to ``case.case_statuses`` and persist.

    Resolves the status object from the DataLayer first; if not found there,
    saves the inline fallback and re-reads so the stored canonical record is
    used.

    Returns SUCCESS on successful append.
    Returns FAILURE if the case or status cannot be resolved.

    Per issue #758 AC-1.
    """

    def __init__(
        self,
        case_id: str,
        status_id: str,
        status_obj_fallback: PersistableModel | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.status_id = status_id
        self.status_obj_fallback = status_obj_fallback

    def _resolve_status(self) -> "PersistableModel | None":
        assert self.datalayer is not None
        status_obj = self.datalayer.read(self.status_id)
        if hasattr(status_obj, "id_"):
            return status_obj
        status_obj = self.status_obj_fallback
        if status_obj is not None:
            self.datalayer.save(status_obj)
            status_obj = self.datalayer.read(self.status_id) or status_obj
        return status_obj if hasattr(status_obj, "id_") else None

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning(
                "AppendCaseStatusToCase: %s", self.feedback_message
            )
            return Status.FAILURE

        status_obj = self._resolve_status()
        if status_obj is None:
            self.feedback_message = f"Status '{self.status_id}' not found"
            self.logger.warning(
                "AppendCaseStatusToCase: %s", self.feedback_message
            )
            return Status.FAILURE

        case.case_statuses.append(status_obj)
        self.datalayer.save(case)
        self.logger.info(
            "AppendCaseStatusToCase: added status '%s' to case '%s'",
            self.status_id,
            self.case_id,
        )
        return Status.SUCCESS
