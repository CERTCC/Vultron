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
SenderSideBT — standard Sequence for participant outbound activities.

Composes three nodes into a Sequence:

    SenderSideBT (Sequence)
    ├─ ResolveCaseManagerNode    # look up CASE_MANAGER actor ID
    ├─ ConstructActivitiesNode   # build AS2 activities via activity_builder
    └─ QueueToOutboxNode         # queue activity IDs to actor outbox

Trigger use cases call ``sender_side_bt()`` after completing their
domain-level work (state transitions, object creation) to handle the
routing and queueing steps consistently.

Per specs/participant-case-replica.yaml PCR-08-001, PCR-08-002.
"""

import logging
from typing import Callable

import py_trees

from vultron.core.behaviors.sender.nodes import (
    ConstructActivitiesNode,
    QueueToOutboxNode,
    ResolveCaseManagerNode,
)

logger = logging.getLogger(__name__)


def sender_side_bt(
    case_id: str,
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Create the SenderSideBT for participant-to-CaseActor messaging.

    Composes :class:`ResolveCaseManagerNode`,
    :class:`ConstructActivitiesNode`, and :class:`QueueToOutboxNode`
    into a ``memory=False`` Sequence.

    The caller must execute the tree via ``BTBridge.execute_with_setup``
    so that ``datalayer`` and ``actor_id`` are written to the blackboard
    before the tree ticks.

    Args:
        case_id: ID of the VulnerabilityCase whose CASE_MANAGER should
            receive the outbound activities.
        activity_builder: ``(case_manager_id: str) -> list[str]`` —
            called by :class:`ConstructActivitiesNode` with the resolved
            CASE_MANAGER actor ID; must create and persist the AS2
            activities and return their IDs.

    Returns:
        Root node of the SenderSideBT Sequence.
    """
    root = py_trees.composites.Sequence(
        name="SenderSideBT",
        memory=False,
        children=[
            ResolveCaseManagerNode(case_id=case_id),
            ConstructActivitiesNode(activity_builder=activity_builder),
            QueueToOutboxNode(),
        ],
    )
    logger.debug(
        "Created SenderSideBT for case_id=%s",
        case_id,
    )
    return root
