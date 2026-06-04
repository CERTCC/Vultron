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
Trigger-side behavior trees for the engage-case and defer-case workflows.

Each tree runs two steps in sequence:

1. **TransitionParticipantRMtoAccepted / TransitionParticipantRMtoDeferred** —
   updates the actor's RM state in the DataLayer (visible in the BT).
2. **sender_side_bt** — resolves the Case Manager, constructs the outbound
   Engage/Defer activity, and queues it in the actor's outbox (PCR-08-001).

This refactoring satisfies #712 AC-1: RM state transitions are performed
inside the BT so they are visible to BT analysis and auditing tools.
"""

from typing import Callable

import py_trees

from vultron.core.behaviors.report.nodes import (
    TransitionParticipantRMtoAccepted,
    TransitionParticipantRMtoDeferred,
)
from vultron.core.behaviors.sender.send_tree import sender_side_bt


def engage_case_trigger_bt(
    case_id: str,
    actor_id: str,
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the engage-case (RM → ACCEPTED) workflow.

    Args:
        case_id: ID of the VulnerabilityCase to engage.
        actor_id: ID of the actor engaging the case; passed to the RM
            transition node (overridden at runtime by the blackboard).
        activity_builder: Callable invoked by the sender subtree with the
            resolved Case Manager actor ID; should return a list of outbound
            activity IDs to queue.

    Returns:
        A ``py_trees.composites.Sequence`` that:

        - Transitions the actor's RM state to ACCEPTED.
        - Resolves the Case Manager, builds the Engage(Case) activity, and
          queues it in the actor's outbox.
    """
    return py_trees.composites.Sequence(
        name="EngageCaseTriggerBT",
        memory=False,
        children=[
            TransitionParticipantRMtoAccepted(
                case_id=case_id, actor_id=actor_id
            ),
            sender_side_bt(case_id=case_id, activity_builder=activity_builder),
        ],
    )


def defer_case_trigger_bt(
    case_id: str,
    actor_id: str,
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the defer-case (RM → DEFERRED) workflow.

    Args:
        case_id: ID of the VulnerabilityCase to defer.
        actor_id: ID of the actor deferring the case; passed to the RM
            transition node (overridden at runtime by the blackboard).
        activity_builder: Callable invoked by the sender subtree with the
            resolved Case Manager actor ID; should return a list of outbound
            activity IDs to queue.

    Returns:
        A ``py_trees.composites.Sequence`` that:

        - Transitions the actor's RM state to DEFERRED.
        - Resolves the Case Manager, builds the Defer(Case) activity, and
          queues it in the actor's outbox.
    """
    return py_trees.composites.Sequence(
        name="DeferCaseTriggerBT",
        memory=False,
        children=[
            TransitionParticipantRMtoDeferred(
                case_id=case_id, actor_id=actor_id
            ),
            sender_side_bt(case_id=case_id, activity_builder=activity_builder),
        ],
    )
