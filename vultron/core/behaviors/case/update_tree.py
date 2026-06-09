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

"""Case update behavior tree composition."""

from __future__ import annotations

import logging

import py_trees

from vultron.core.behaviors.case.nodes.update import (
    ApplyCaseUpdateNode,
    BroadcastCaseUpdateNode,
    CaptureCaseUpdateBroadcastExclusionsNode,
    CheckCaseUpdateOwnerNode,
)
from vultron.core.models.events.case import UpdateCaseReceivedEvent

logger = logging.getLogger(__name__)


def create_update_case_received_tree(
    case_id: str,
    actor_id: str,
    request: UpdateCaseReceivedEvent,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for UpdateCaseReceivedUseCase."""
    root = py_trees.composites.Sequence(
        name="UpdateCaseBT",
        memory=False,
        children=[
            CheckCaseUpdateOwnerNode(case_id=case_id),
            CaptureCaseUpdateBroadcastExclusionsNode(case_id=case_id),
            ApplyCaseUpdateNode(case_id=case_id, request=request),
            BroadcastCaseUpdateNode(case_id=case_id),
        ],
    )
    logger.info(
        "Created UpdateCaseBT for case=%s, actor=%s", case_id, actor_id
    )
    return root
