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

"""Case lifecycle trigger nodes for DEMOMA-07-003 steps 4–5.

Contains the public-disclosure embargo teardown branch (step 4) and the
auto-close emit node (step 5).  The auto-close precondition and idempotency
guards are in ``conditions.py``; the routing guard is
:class:`~vultron.core.behaviors.sender.nodes.actions.ResolveCaseManagerNode`.
"""

import logging
from typing import cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.protocols import PersistableModel
from vultron.enums.roles import CVDRole
from vultron.core.models._helpers import _as_id

logger = logging.getLogger(__name__)


class _PublicDisclosureSkipConditionNode(DataLayerCondition):
    """Inner guard for :class:`PublicDisclosureBranchNode`.

    Returns SUCCESS (skip teardown) when:
    - The new status is NOT public-aware (CS.P not set), OR
    - DataLayer or case_id is unavailable, OR
    - The sender is not a known case participant, OR
    - The sender does NOT hold the CASE_OWNER role, OR
    - The case has no active embargo (nothing to terminate).

    Returns FAILURE (proceed to teardown) when the sender IS a CASE_OWNER
    who has sent a public-aware status update AND the case has an active embargo.
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

        case_status: object = getattr(self.status_obj, "case_status", None)
        if case_status is None:
            pxa_state = None
        elif hasattr(case_status, "pxa"):
            pxa_state = getattr(case_status, "pxa").state
        elif hasattr(case_status, "pxa_state"):
            pxa_state = getattr(case_status, "pxa_state")
        else:
            pxa_state = None
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

    def _sender_is_case_owner(self, case: VulnerabilityCase) -> bool:
        """Return True iff sender is a known CASE_OWNER participant."""
        assert self.datalayer is not None
        sender_participant_id = case.actor_participant_index.get(
            self.sender_actor_id
        )
        if sender_participant_id is None:
            return False
        sender_participant = self.datalayer.read(sender_participant_id)
        roles = (
            sender_participant.roles
            if isinstance(sender_participant, CaseParticipant)
            else []
        )
        return CVDRole.CASE_OWNER in roles

    def update(self) -> Status:
        if not self._public_aware():
            return Status.SUCCESS

        if self.datalayer is None or not self.case_id:
            return Status.SUCCESS

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            return Status.SUCCESS

        if not self._sender_is_case_owner(case):
            return Status.SUCCESS

        if _as_id(case.active_embargo) is None:
            return Status.SUCCESS

        # Condition met: sender is CASE_OWNER reporting public awareness AND
        # there is an active embargo to terminate.
        return Status.FAILURE


class PublicDisclosureBranchNode(py_trees.composites.Selector):
    """Step 4: Trigger embargo teardown if public disclosure is detected.

    Condition: the new ParticipantStatus has CS.P (public-aware) set AND
    the sender holds the CASE_OWNER role.

    When the condition is met, delegates to the shared ``terminate_embargo_bt``
    factory (BT-19-002), which places the routing guard before the EM state
    mutation.  Skips silently if conditions are not met.

    Returns SUCCESS when teardown conditions are not met (skip path) or
    when teardown completes and the broadcast activity is queued.
    Returns FAILURE when teardown is needed but routing prerequisites are
    absent or the activity cannot be dispatched (BT-14-001, BT-19-001).

    Implemented as a ``py_trees.composites.Selector`` (memory=False):

    - Child 1 ``_PublicDisclosureSkipConditionNode``: SUCCESS → skip teardown.
    - Child 2 ``TerminateEmbargoBT``: SUCCESS on success; FAILURE when routing
      prerequisites are absent or dispatch fails (BT-14-001).

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
        result_out: dict[str, object] = {}
        terminate_subtree = (
            terminate_embargo_bt(
                case_id=case_id,
                result_out=result_out,
            )
            if case_id is not None
            else py_trees.behaviours.Success(name="TerminateEmbargoSkipped")
        )
        self.add_children(
            [
                _PublicDisclosureSkipConditionNode(
                    status_obj=status_obj,
                    sender_actor_id=sender_actor_id,
                    case_id=case_id,
                    name="SkipCondition",
                ),
                terminate_subtree,
            ]
        )


class EmitAddCaseStatusToSelfNode(DataLayerAction):
    """Emit a self-addressed ``Add(CaseStatus, VulnerabilityCase)`` to the CaseActor.

    When ``StatusUpdateGuard`` passes (RSH-01-003), this node:

    1. Reads the ``ParticipantStatus`` from the DataLayer by ``participant_status_id``.
    2. Extracts its embedded ``case_status`` field (an ``as_CaseStatus`` or
       ``CaseStatus``).  If the case status is absent, returns FAILURE.
    3. Ensures the case status is persisted (creates it if not already in the DL).
    4. Calls ``trigger_activity_factory.add_case_status_to_case()`` addressed to
       the executing actor itself (self-addressed: actor == to == CaseActor).
    5. Queues the resulting activity in the actor's outbox.

    The self-addressed activity routes through
    ``AddCaseStatusToCaseReceivedUseCase`` → ``add_case_status_tree``, where
    the canonical write and side-effects (Seam 2) execute.  This pattern
    decouples Seam 1 (adoption authorization) from Seam 2 (side-effects).

    Returns ``FAILURE`` when:
    - ``trigger_activity_factory`` is absent (BT-14-001).
    - ``participant_status_id`` or ``case_id`` are empty.
    - The ``ParticipantStatus`` has no embedded ``case_status``.
    - The factory raises an exception.

    Returns ``SUCCESS`` when the activity is created and queued.

    Per RSH-01-003, ADR-0046.
    """

    def __init__(
        self,
        participant_status_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.participant_status_id = participant_status_id
        self.case_id = case_id

    def _resolve_case_status_id(self) -> "str | None":
        """Read ParticipantStatus and persist its embedded CaseStatus.

        Returns the persisted CaseStatus ID, or None on failure.
        """
        assert self.datalayer is not None

        participant_status = self.datalayer.read(self.participant_status_id)
        if participant_status is None:
            self.logger.warning(
                "EmitAddCaseStatusToSelf: ParticipantStatus '%s' not found",
                self.participant_status_id,
            )
            return None

        case_status = getattr(participant_status, "case_status", None)
        if case_status is None:
            self.logger.debug(
                "EmitAddCaseStatusToSelf: ParticipantStatus '%s' has no"
                " embedded case_status — skipping emit",
                self.participant_status_id,
            )
            return None

        case_status_id = getattr(case_status, "id_", None)
        if not case_status_id:
            self.logger.warning(
                "EmitAddCaseStatusToSelf: embedded case_status has no id_"
            )
            return None

        # Persist the case status so the factory can read it back.
        try:
            self.datalayer.create(case_status)
        except ValueError:
            pass  # already exists — idempotent

        return str(case_status_id)

    def update(self) -> Status:
        if not self.participant_status_id or not self.case_id:
            self.feedback_message = "EmitAddCaseStatusToSelf: missing participant_status_id or case_id"
            self.logger.warning(self.feedback_message)
            return Status.FAILURE

        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        if (f := self._require_factory()) is not None:
            self.logger.warning(
                "EmitAddCaseStatusToSelf: no TriggerActivityPort — cannot"
                " emit Add(CaseStatus) for case '%s'",
                self.case_id,
            )
            return f

        case_status_id = self._resolve_case_status_id()
        if case_status_id is None:
            # No embedded CaseStatus — no canonical update to emit; soft skip.
            self.feedback_message = (
                "EmitAddCaseStatusToSelf: no embedded case_status to emit"
            )
            self.logger.debug(self.feedback_message)
            return Status.FAILURE

        assert self.trigger_activity_factory is not None
        try:
            # Self-addressed: actor and to are both the executing CaseActor.
            activity_id = (
                self.trigger_activity_factory.add_case_status_to_case(
                    status_id=case_status_id,
                    case_id=self.case_id,
                    actor=self.actor_id,
                    to=[self.actor_id],
                )
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            self.logger.info(
                "EmitAddCaseStatusToSelf: queued Add(CaseStatus) '%s'"
                " to self '%s' for case '%s' (RSH-01-003)",
                activity_id,
                self.actor_id,
                self.case_id,
            )
        except Exception as e:
            self.feedback_message = (
                f"EmitAddCaseStatusToSelf: failed to emit Add(CaseStatus): {e}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        return Status.SUCCESS


class EmitCloseCaseNode(DataLayerAction):
    """Step 5 emit: Queue a ``Leave(VulnerabilityCase)`` to the Case Manager.

    Reads ``case_manager_id`` from the blackboard (written by the preceding
    :class:`~vultron.core.behaviors.sender.nodes.actions.ResolveCaseManagerNode`)
    and calls ``trigger_activity_factory.close_case(...)`` to create and queue
    the activity.

    Returns SUCCESS when the activity is queued successfully or when
    ``trigger_activity_factory`` is absent (best-effort: receive-side paths
    intentionally omit the factory).
    Returns FAILURE only on an unexpected exception during activity creation.

    Per DEMOMA-07-003 step 5, DEMOMA-07-006.
    """

    def __init__(
        self,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_manager_id",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if self.datalayer is None or not self.case_id:
            return Status.SUCCESS

        if self.trigger_activity_factory is None:
            self.logger.warning(
                "EmitCloseCase: no TriggerActivityPort — cannot emit"
                " Leave(VulnerabilityCase) for case '%s'",
                self.case_id,
            )
            return Status.SUCCESS

        try:
            case_manager_id: str | None = self.blackboard.get(
                "case_manager_id"
            )
        except KeyError:
            case_manager_id = None
        if not case_manager_id:
            self.feedback_message = (
                f"EmitCloseCase: case_manager_id not set on blackboard"
                f" for case '{self.case_id}' — cannot emit"
            )
            self.logger.warning(self.feedback_message)
            return Status.SUCCESS

        try:
            activity_id, _ = self.trigger_activity_factory.close_case(
                case_id=self.case_id,
                actor=self.actor_id or "",
                to=[case_manager_id],
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id or "", activity_id
            )
            self.logger.info(
                "EmitCloseCase: queued Leave(VulnerabilityCase) '%s'"
                " to CaseActor '%s' (DEMOMA-07-003 step 5)",
                activity_id,
                case_manager_id,
            )
        except Exception as e:
            self.feedback_message = (
                f"EmitCloseCase: failed to emit close_case: {e}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        return Status.SUCCESS
