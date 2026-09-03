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

"""Participant verification condition nodes for status workflows.

Contains the sender-is-participant guard node used as step 1 of the
AddParticipantStatusToParticipant workflow (DEMOMA-07-003), and the
two precondition nodes extracted from AutoCloseBranchNode per DEMOMA-07-006:
AllParticipantsRMClosedConditionNode and CloseNotYetEmittedConditionNode.
"""

import logging
from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    FindParticipantByActorIdNode,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.states.rm import RM

logger = logging.getLogger(__name__)


class VerifySenderIsParticipantNode(FindParticipantByActorIdNode):
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
        super().__init__(
            case_id=case_id or "",
            target_actor_id=sender_actor_id,
            participant_key="sender_participant",
            name=name or self.__class__.__name__,
        )
        self.status_id = status_id
        self.sender_actor_id = sender_actor_id
        self._case_id_hint = case_id

    def _resolve_case_id(self) -> str | None:
        if self._case_id_hint:
            return self._case_id_hint
        assert self.datalayer is not None
        status_raw = self.datalayer.read(self.status_id)
        if status_raw is None:
            return None
        context = getattr(status_raw, "context", None)
        return str(context) if context else None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f

        case_id = self._resolve_case_id()
        if case_id is None:
            self.feedback_message = (
                f"Cannot determine case_id for status '{self.status_id}'"
            )
            self.logger.warning(
                "VerifySenderIsParticipant: %s", self.feedback_message
            )
            return Status.FAILURE

        self.case_id = case_id
        result = super().update()
        if result == Status.FAILURE:
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


class AllParticipantsRMClosedConditionNode(DataLayerConditionWithPorts):
    """Precondition: all CVD participants in the case have RM.CLOSED.

    Iterates ``case.actor_participant_index`` and returns ``FAILURE`` if any
    participant's latest status ``rm_state`` is not ``RM.CLOSED``.  Returns
    ``SUCCESS`` when every participant (including the Case Actor) is at
    ``RM.CLOSED``.

    The Case Actor now has a full RM lifecycle (ADR-0051, CM-23-005), so the
    former ``CVDRole.CASE_MANAGER`` skip is no longer needed.  Including the
    Case Actor's RM.CLOSED in this check ensures that owner-Leave processing
    (CM-23-002) has completed before the auto-close Selector fires.

    Per DEMOMA-07-006(a)(b)(c).
    """

    def __init__(
        self,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def _all_participants_closed(self, case: Any) -> bool:
        assert self.datalayer is not None
        if not case.actor_participant_index:
            return False
        for p_id in case.actor_participant_index.values():
            p = self.datalayer.read(p_id)
            if p is None:
                return False
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
            if not isinstance(latest, ParticipantStatus):
                return False
            if latest.rm.state != RM.CLOSED:
                return False
        return True

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if not self.case_id:
            self.feedback_message = "No case_id — skipping auto-close check"
            return Status.FAILURE

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        if not self._all_participants_closed(case):
            self.feedback_message = (
                "Not all participants are RM.CLOSED — skipping auto-close"
            )
            return Status.FAILURE

        self.logger.debug(
            "AllParticipantsRMClosed: all CVD participants are RM.CLOSED"
            " for case '%s' (DEMOMA-07-006)",
            self.case_id,
        )
        return Status.SUCCESS


class CloseNotYetEmittedConditionNode(DataLayerConditionWithPorts):
    """Idempotency guard: no ``Leave(VulnerabilityCase)`` in the outbox yet.

    Queries the actor's outbox for existing activities and checks whether any
    is a ``Leave`` activity targeting ``self.case_id``.  Returns ``FAILURE``
    (skip) when a ``Leave(VulnerabilityCase)`` has already been queued, or
    ``SUCCESS`` when none has been emitted yet.

    Uses the DataLayer outbox — not a process-level in-memory set — so the
    check survives process restarts and is visible to the BT audit trail.

    Per DEMOMA-07-006 idempotency requirement.
    """

    def __init__(
        self,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        if not self.case_id:
            self.feedback_message = "No case_id — cannot check idempotency"
            return Status.FAILURE

        outbox_port = cast(CaseOutboxPersistence, self.datalayer)
        activity_ids = outbox_port.outbox_list()

        for activity_id in activity_ids:
            activity = self.datalayer.read(activity_id)
            if activity is None:
                continue
            activity_type = getattr(activity, "type_", None)
            if activity_type != "Leave":
                continue
            obj = getattr(activity, "object_", None)
            obj_id = _as_id(obj) if obj is not None else None
            if obj_id == self.case_id:
                self.feedback_message = (
                    f"Leave(VulnerabilityCase) already emitted for case"
                    f" '{self.case_id}' — skipping duplicate"
                )
                self.logger.debug(
                    "CloseNotYetEmitted: %s", self.feedback_message
                )
                return Status.FAILURE

        self.logger.debug(
            "CloseNotYetEmitted: no prior Leave(VulnerabilityCase) in outbox"
            " for case '%s' — proceeding",
            self.case_id,
        )
        return Status.SUCCESS
