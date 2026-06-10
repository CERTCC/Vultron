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
Case prioritization behavior tree composition.

This module composes the engage_case and defer_case workflows as behavior
trees. These handle the receive-side of RmEngageCaseActivity (Join(VulnerabilityCase))
and RmDeferCaseActivity (Ignore(VulnerabilityCase)) activities.

Background: RM is a participant-specific state machine. Each CaseParticipant
wraps an Actor within a case and carries its own RM state via
CaseParticipant.participant_status[].rm_state. The trees here update that
state when an actor notifies us they have engaged or deferred the case.

Per specs/behavior-tree-integration.yaml BT-06 requirements.

Structure:

    EngageCaseBT (Sequence)
    ├─ CheckParticipantExists              # Precondition: actor has a participant record
    ├─ TransitionParticipantRMtoAccepted   # Update RM state to ACCEPTED
    └─ CommitCaseLogEntryNode              # Log entry → Announce fan-out (SYNC-02-002)

    DeferCaseBT (Sequence)
    ├─ CheckParticipantExists              # Precondition: actor has a participant record
    ├─ TransitionParticipantRMtoDeferred   # Update RM state to DEFERRED
    └─ CommitCaseLogEntryNode              # Log entry → Announce fan-out (SYNC-02-002)

Note: EvaluateCasePriority (in nodes.py) is the stub node for the outgoing
direction — when the local actor decides whether to engage or defer. It is
not used in these receive-side trees but is exported for future use.
"""

import logging

import py_trees

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.case.nodes import CommitCaseLogEntryNode
from vultron.core.behaviors.report.nodes import (
    CheckParticipantExists,
    EvaluateCasePriority,
    TransitionParticipantRMtoAccepted,
    TransitionParticipantRMtoDeferred,
)
from vultron.core.models.protocols import is_case_model
from vultron.core.behaviors.sender.nodes import QueueToOutboxNode
from vultron.core.use_cases._helpers import case_addressees

logger = logging.getLogger(__name__)


class ResolveCaseAddresseesNode(DataLayerAction):
    """Resolve outbound addressees for report prioritization."""

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_addressees",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> py_trees.common.Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return py_trees.common.Status.FAILURE

        try:
            case = self.datalayer.read(self.case_id)
            if not is_case_model(case):
                self.feedback_message = (
                    f"Case '{self.case_id}' not found or wrong type"
                )
                return py_trees.common.Status.FAILURE

            addressees = case_addressees(case, self.actor_id)
        except Exception as exc:
            self.feedback_message = (
                f"Failed to resolve report addressees: {exc}"
            )
            return py_trees.common.Status.FAILURE

        self.blackboard.case_addressees = addressees
        return py_trees.common.Status.SUCCESS


class EmitCasePriorityActivityNode(DataLayerAction):
    """Create and queue report-priority outbound activities."""

    def __init__(
        self,
        case_id: str,
        activity_method: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._activity_method = activity_method

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_addressees",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="activity_ids",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> py_trees.common.Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return py_trees.common.Status.FAILURE

        factory = self.trigger_activity_factory
        if factory is None:
            self.feedback_message = "trigger_activity_factory not available"
            return py_trees.common.Status.FAILURE

        try:
            addressees = self.blackboard.case_addressees
        except KeyError:
            self.feedback_message = "case_addressees not in blackboard"
            return py_trees.common.Status.FAILURE

        to = addressees or None

        activity_method = getattr(factory, self._activity_method, None)
        if activity_method is None:
            self.feedback_message = (
                f"TriggerActivityPort missing '{self._activity_method}'"
            )
            return py_trees.common.Status.FAILURE

        try:
            activity_id, _ = activity_method(
                case_id=self.case_id,
                actor=self.actor_id,
                to=to,
            )
        except Exception as exc:
            self.feedback_message = (
                f"Failed to emit report-priority activity: {exc}"
            )
            return py_trees.common.Status.FAILURE

        self.blackboard.activity_ids = [activity_id]
        return py_trees.common.Status.SUCCESS


def _create_sender_side_bt(
    case_id: str,
    activity_method: str,
) -> py_trees.behaviour.Behaviour:
    return py_trees.composites.Sequence(
        name="SenderSideBT",
        memory=False,
        children=[
            ResolveCaseAddresseesNode(case_id=case_id),
            EmitCasePriorityActivityNode(
                case_id=case_id,
                activity_method=activity_method,
            ),
            QueueToOutboxNode(),
        ],
    )


def create_engage_case_tree(
    case_id: str,
    actor_id: str,
) -> py_trees.behaviour.Behaviour:
    """
    Create behavior tree for the engage_case workflow.

    Handles receipt of RmEngageCaseActivity (Join(VulnerabilityCase)): the sending
    actor has decided to engage the case, so we record their RM state
    transition to ACCEPTED in their CaseParticipant.participant_status.

    Args:
        case_id: ID of VulnerabilityCase being engaged
        actor_id: ID of Actor whose RM state transitions to ACCEPTED

    Returns:
        Root node of the engage_case behavior tree (Sequence)
    """
    root = py_trees.composites.Sequence(
        name="EngageCaseBT",
        memory=False,
        children=[
            CheckParticipantExists(case_id=case_id, actor_id=actor_id),
            TransitionParticipantRMtoAccepted(
                case_id=case_id, actor_id=actor_id
            ),
            CommitCaseLogEntryNode(case_id=case_id),
        ],
    )

    logger.info(f"Created EngageCaseBT for case={case_id}, actor={actor_id}")
    return root


def create_defer_case_tree(
    case_id: str,
    actor_id: str,
) -> py_trees.behaviour.Behaviour:
    """
    Create behavior tree for the defer_case workflow.

    Handles receipt of RmDeferCaseActivity (Ignore(VulnerabilityCase)): the sending
    actor has decided to defer the case, so we record their RM state
    transition to DEFERRED in their CaseParticipant.participant_status.

    Args:
        case_id: ID of VulnerabilityCase being deferred
        actor_id: ID of Actor whose RM state transitions to DEFERRED

    Returns:
        Root node of the defer_case behavior tree (Sequence)
    """
    root = py_trees.composites.Sequence(
        name="DeferCaseBT",
        memory=False,
        children=[
            CheckParticipantExists(case_id=case_id, actor_id=actor_id),
            TransitionParticipantRMtoDeferred(
                case_id=case_id, actor_id=actor_id
            ),
            CommitCaseLogEntryNode(case_id=case_id),
        ],
    )

    logger.info(f"Created DeferCaseBT for case={case_id}, actor={actor_id}")
    return root


def create_prioritize_subtree(
    case_id: str,
    actor_id: str,
) -> py_trees.behaviour.Behaviour:
    """
    Create behavior tree subtree for case prioritization (engage or defer).

    Phase 1: EvaluateCasePriority always returns SUCCESS → engage path.
    Future: Plug in SSVC or other priority evaluator (IDEA-26041004).

    Structure::

        PrioritizeBT (Selector)
        ├─ EngagePath (Sequence)
        │    ├─ EvaluateCasePriority      # stub: SUCCESS = engage
        │    ├─ SenderSideBT              # resolve case manager and emit Join
        │    └─ TransitionParticipantRMtoAccepted  # RM → ACCEPTED
        └─ DeferPath (Sequence)
             ├─ SenderSideBT              # resolve case manager and emit Ignore
             └─ TransitionParticipantRMtoDeferred   # RM → DEFERRED

    Per specs/behavior-tree-integration.yaml BT-06-005, BT-06-006.
    This is the SSVC evaluator connection point (IDEA-26041004).

    Args:
        case_id: ID of VulnerabilityCase to prioritize
        actor_id: ID of Actor making the engage/defer decision

    Returns:
        Root node of the prioritize behavior tree (Selector)
    """
    engage_path = py_trees.composites.Sequence(
        name="EngagePath",
        memory=False,
        children=[
            EvaluateCasePriority(case_id=case_id),
            _create_sender_side_bt(
                case_id=case_id,
                activity_method="engage_case",
            ),
            TransitionParticipantRMtoAccepted(
                case_id=case_id, actor_id=actor_id
            ),
        ],
    )
    defer_path = py_trees.composites.Sequence(
        name="DeferPath",
        memory=False,
        children=[
            _create_sender_side_bt(
                case_id=case_id,
                activity_method="defer_case",
            ),
            TransitionParticipantRMtoDeferred(
                case_id=case_id, actor_id=actor_id
            ),
        ],
    )
    root = py_trees.composites.Selector(
        name="PrioritizeBT",
        memory=False,
        children=[engage_path, defer_path],
    )
    logger.info(f"Created PrioritizeBT for case={case_id}, actor={actor_id}")
    return root
