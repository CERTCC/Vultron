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

Per specs/behavior-tree-integration.md BT-06 requirements.

Structure:

    EngageCaseBT (Sequence)
    ├─ CheckParticipantExists        # Precondition: actor has a participant record
    └─ TransitionParticipantRMtoAccepted  # Update RM state to ACCEPTED

    DeferCaseBT (Sequence)
    ├─ CheckParticipantExists        # Precondition: actor has a participant record
    └─ TransitionParticipantRMtoDeferred  # Update RM state to DEFERRED

Note: EvaluateCasePriority (in nodes.py) is the stub node for the outgoing
direction — when the local actor decides whether to engage or defer. It is
not used in these receive-side trees but is exported for future use.
"""

import logging

import py_trees

from vultron.core.behaviors.report.nodes import (
    CheckParticipantExists,
    EmitDeferCaseActivity,
    EmitEngageCaseActivity,
    EvaluateCasePriority,
    TransitionParticipantRMtoAccepted,
    TransitionParticipantRMtoDeferred,
)

logger = logging.getLogger(__name__)


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
        ],
    )

    logger.debug(f"Created EngageCaseBT for case={case_id}, actor={actor_id}")
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
        ],
    )

    logger.debug(f"Created DeferCaseBT for case={case_id}, actor={actor_id}")
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
        │    ├─ EmitEngageCaseActivity    # emit RmEngageCaseActivity
        │    └─ TransitionParticipantRMtoAccepted  # RM → ACCEPTED
        └─ DeferPath (Sequence)
             ├─ EmitDeferCaseActivity     # emit RmDeferCaseActivity
             └─ TransitionParticipantRMtoDeferred   # RM → DEFERRED

    Per specs/behavior-tree-integration.md BT-06-005, BT-06-006.
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
            EmitEngageCaseActivity(case_id=case_id, actor_id=actor_id),
            TransitionParticipantRMtoAccepted(
                case_id=case_id, actor_id=actor_id
            ),
        ],
    )
    defer_path = py_trees.composites.Sequence(
        name="DeferPath",
        memory=False,
        children=[
            EmitDeferCaseActivity(case_id=case_id, actor_id=actor_id),
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
    logger.debug(f"Created PrioritizeBT for case={case_id}, actor={actor_id}")
    return root
