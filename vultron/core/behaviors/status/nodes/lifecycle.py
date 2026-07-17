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
all-participants-closed auto-close branch (step 5).
"""

import logging
import threading
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.use_cases._helpers import _resolve_case_manager_id
from vultron.core.models.protocols import (
    PersistableModel,
    is_case_model,
    is_participant_model,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.core.use_cases._helpers import _as_id

logger = logging.getLogger(__name__)

# Guard against AutoCloseBranchNode firing more than once per case.
# Keyed by case_id — the first BT execution to observe all-participants-CLOSED
# for a given case wins; subsequent ones are no-ops for that case.
# Protected by a threading.Lock because FastAPI BackgroundTasks run on a
# thread pool (see AGENTS.md: "BTBridge Thread-Safety (RLock)").
_auto_close_lock: threading.Lock = threading.Lock()
_auto_close_triggered: set[str] = set()  # case_ids that have fired AutoClose


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
        roles = (
            sender_participant.roles
            if is_participant_model(sender_participant)
            else []
        )
        if CVDRole.CASE_OWNER not in roles:
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
            roles = p.roles if is_participant_model(p) else []
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

    def _emit_close_case(self, actor_id: str, case_manager_id: str) -> str:
        """Call close_case factory and record outbox item, return activity_id.

        Raises on factory or outbox failure so update() can log and continue.
        """
        assert self.trigger_activity_factory is not None
        assert self.datalayer is not None
        assert self.case_id is not None
        activity_id, _ = self.trigger_activity_factory.close_case(
            case_id=self.case_id,
            actor=actor_id,
            to=[case_manager_id],
        )
        cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
            actor_id, activity_id
        )
        return activity_id

    def update(self) -> Status:
        if self.datalayer is None or not self.case_id:
            return Status.SUCCESS

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            return Status.SUCCESS
        if not self._all_participants_closed(case):
            return Status.SUCCESS

        with _auto_close_lock:
            if self.case_id in _auto_close_triggered:
                self.logger.debug(
                    "AutoCloseBranch: close_case already triggered for"
                    " case '%s' — skipping duplicate fire",
                    self.case_id,
                )
                return Status.SUCCESS
            _auto_close_triggered.add(self.case_id)

        case_manager_id = _resolve_case_manager_id(case, self.datalayer)
        if case_manager_id is None:
            self.logger.warning(
                "AutoCloseBranch: no Case Manager found"
                " — cannot auto-close case '%s'",
                self.case_id,
            )
            return Status.SUCCESS

        self.logger.info(
            "AutoCloseBranch: all participants CLOSED for case '%s'"
            " — emitting Leave(VulnerabilityCase) to CaseActor '%s'"
            " (DEMOMA-07-003 step 5)",
            self.case_id,
            case_manager_id,
        )
        if self.trigger_activity_factory is None:
            self.logger.warning(
                "AutoCloseBranch: no TriggerActivityPort — cannot emit"
                " close_case activity for case '%s'",
                self.case_id,
            )
            return Status.SUCCESS

        try:
            activity_id = self._emit_close_case(
                self.actor_id or "", case_manager_id
            )
            self.logger.info(
                "AutoCloseBranch: emitted close_case activity '%s'"
                " to CaseActor '%s'",
                activity_id,
                case_manager_id,
            )
        except Exception as e:
            self.logger.error(
                "AutoCloseBranch: failed to emit close_case: %s", e
            )

        return Status.SUCCESS
