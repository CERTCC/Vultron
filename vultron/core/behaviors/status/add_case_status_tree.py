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
AddCaseStatus behavior tree composition.

Composes the three-step AddCaseStatus workflow as a Sequence BT:

    AddCaseStatusToCaseBT (Sequence)
    ├─ CheckCaseStatusIdempotencyNode   # AC-1: status not already present
    ├─ ValidateCaseStatusTransitionNode # AC-2: EM/PXA transitions are valid
    └─ AppendCaseStatusToCaseNode       # AC-1: append status and persist

Per issue #758 (BT-SM Integration: AddCaseStatusToCaseReceivedUseCase).
"""

import logging

import py_trees

from vultron.core.models.events.status import AddCaseStatusToCaseReceivedEvent
from vultron.core.behaviors.status.nodes import (
    AppendCaseStatusToCaseNode,
    CheckCaseStatusIdempotencyNode,
    ValidateCaseStatusTransitionNode,
)

logger = logging.getLogger(__name__)


def add_case_status_tree(
    request: AddCaseStatusToCaseReceivedEvent,
) -> py_trees.behaviour.Behaviour:
    """Create the behavior tree for the AddCaseStatusToCase workflow.

    Handles receipt of an ``Add(CaseStatus, VulnerabilityCase)`` activity.
    Implements three steps as BT nodes in a Sequence:

    1. Idempotency check — fail fast if the status is already present.
    2. Transition validation — reject invalid EM or PXA state transitions.
    3. Append and persist — write the new CaseStatus to the case record.

    Args:
        request: The parsed inbound domain event.

    Returns:
        Root node of the ``AddCaseStatusToCaseBT`` Sequence.
    """
    status_id = request.status_id or ""
    case_id = request.case_id or ""
    status_obj = request.status

    root = py_trees.composites.Sequence(
        name="AddCaseStatusToCaseBT",
        memory=False,
        children=[
            CheckCaseStatusIdempotencyNode(
                case_id=case_id,
                status_id=status_id,
            ),
            ValidateCaseStatusTransitionNode(
                case_id=case_id,
                status_id=status_id,
                status_obj_fallback=status_obj,
            ),
            AppendCaseStatusToCaseNode(
                case_id=case_id,
                status_id=status_id,
                status_obj_fallback=status_obj,
            ),
        ],
    )
    logger.debug(
        "Created AddCaseStatusToCaseBT for status=%s case=%s actor=%s",
        status_id,
        case_id,
        request.actor_id,
    )
    return root
