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
AnnounceEmbargoTeardown behavior tree composition.

Composes the receiver-side embargo teardown workflow as a Sequence BT:

    AnnounceEmbargoTeardownBT (Sequence)
    ├─ ValidateCaseExistsNode    # case must exist and pass is_case_model
    └─ ApplyEmbargoTeardownNode  # ACTIVE→EXITED, clear embargo, reset PEC

Invoked by ``AnnounceEmbargoEventToCaseReceivedUseCase`` on receipt of an
``Announce(EmbargoEvent)`` activity.

Per specs/behavior-tree-integration.yaml BT-06-001.
"""

import logging

import py_trees

from vultron.core.behaviors.embargo.nodes import (
    ApplyEmbargoTeardownNode,
    ValidateCaseExistsNode,
)

logger = logging.getLogger(__name__)


def announce_embargo_teardown_tree(
    case_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the behavior tree for receive-side embargo teardown.

    Handles receipt of an ``Announce(EmbargoEvent)`` activity.  Applies
    the ACTIVE/REVISE → EXITED EM state transition, clears
    ``active_embargo``, and resets participant embargo consent states.

    Args:
        case_id: ID of the VulnerabilityCase to update.

    Returns:
        Root node of the ``AnnounceEmbargoTeardownBT`` Sequence.
    """
    root = py_trees.composites.Sequence(
        name="AnnounceEmbargoTeardownBT",
        memory=False,
        children=[
            ValidateCaseExistsNode(case_id=case_id),
            ApplyEmbargoTeardownNode(case_id=case_id),
        ],
    )
    logger.debug(
        "Created AnnounceEmbargoTeardownBT for case=%s",
        case_id,
    )
    return root
