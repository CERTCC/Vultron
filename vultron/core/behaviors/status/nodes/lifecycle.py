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
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes import TerminateEmbargoNode
from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.behaviors.status.nodes.broadcast import _find_case_manager_id
from vultron.core.models.protocols import PersistableModel, is_case_model
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases._helpers import _as_id

logger = logging.getLogger(__name__)


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

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        try:
            self.blackboard.register_key(
                key="activity", access=py_trees.common.Access.READ
            )
        except Exception:
            pass

    def _receiving_actor_id(self) -> str | None:
        """Read ``activity.receiving_actor_id`` from the blackboard, if any.

        On received-side BT executions, ``self.actor_id`` is the AS2
        **sender's** id (from ``activity.actor``), not the DataLayer-owning
        actor.  ``activity.receiving_actor_id`` carries the canonical id of
        the actor whose DataLayer is being mutated and is set by the inbox
        router (CLP-07).
        """
        try:
            activity = self.blackboard.activity
        except (KeyError, AttributeError):
            return None
        return getattr(activity, "receiving_actor_id", None)

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

        # Canonical ledger is owned exclusively by the Case Actor (ADR-0019,
        # CLP-07).  Only commit when this BT execution is running on the Case
        # Actor's own DataLayer; participant replicas receive the entry via
        # Announce(CaseLedgerEntry).  Without this guard, every participant
        # (finder, vendor, case-actor) would commit its own local close_case
        # entry at its own logIndex, producing cross-actor hash divergence
        # (invariants 2/3) and replication gaps (invariants 8/14).
        #
        # ``self.actor_id`` is the AS2 sender's id (the Case Actor for
        # received broadcasts), so it cannot distinguish "running on the
        # Case Actor's DataLayer" from "running on a participant's DataLayer
        # that just received the Case Actor's broadcast".  Use the receiving
        # actor id (the DataLayer-owning actor) instead.
        receiving_actor_id = self._receiving_actor_id()
        if (
            receiving_actor_id is not None
            and receiving_actor_id != case_manager_id
        ):
            return Status.SUCCESS

        self._commit_close_case_ledger_entry(
            case_id=self.case_id,
            case_actor_id=case_manager_id,
        )
        return Status.SUCCESS

    def _commit_close_case_ledger_entry(
        self, *, case_id: str, case_actor_id: str
    ) -> None:
        """Commit a canonical ``close_case`` ledger entry (BT-15-001).

        Uses ``commit_log_entry_trigger`` directly since the fan-out
        happens within the same BTBridge execution context.
        """
        from typing import cast

        from vultron.core.ports.case_persistence import CaseOutboxPersistence
        from vultron.core.use_cases.triggers.sync import (
            commit_log_entry_trigger,
        )

        if self.datalayer is None:
            return

        payload_snapshot = {
            "type": "Announce",
            "actor": case_actor_id,
            "context": case_id,
            "object": {"type": "VulnerabilityCase", "id": case_id},
        }
        try:
            commit_log_entry_trigger(
                case_id=case_id,
                object_id=case_id,
                event_type="close_case",
                actor_id=case_actor_id,
                dl=cast(CaseOutboxPersistence, self.datalayer),
                payload_snapshot=payload_snapshot,
            )
        except Exception:
            self.logger.warning(
                "AutoCloseBranch: failed to commit close_case ledger entry"
                " for case '%s'",
                case_id,
                exc_info=True,
            )
