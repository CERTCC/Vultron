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

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
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
    """Create the BT for UpdateCaseReceivedUseCase.

    Structure::

        UpdateCaseBT (Sequence)
        ├── CheckCaseUpdateOwnerNode        (gates on the *sender*)
        ├── CaptureCaseUpdateBroadcastExclusionsNode
        ├── ApplyCaseUpdateNode
        └── GuardedBroadcastCaseUpdateBT (Selector)
            ├── SkipIfNotCaseManager (Sequence)
            │   └── Inverter(CheckIsCaseManagerNode)
            └── BroadcastCaseUpdateNode

    Every actor applies the update to its own replica; only the case's
    ``CASE_MANAGER`` announces it (CM-06-001).  The gate is on the **role**
    resolved from the case — not on a comparison against a separately computed
    CaseActor id — because the authority is a role held in the case and its
    holder may be any Actor type.  This mirrors CLP-09, which already role-gates
    canonical ledger commits: appending to the log and announcing the append are
    one privilege.

    Ungated, any actor processing an ``Update(VulnerabilityCase)`` would emit an
    ``Announce`` authored as itself to every participant, which for a
    non-authoritative actor is identity spoofing.  A non-manager therefore
    *skips* the broadcast (Success) rather than failing: applying the update
    locally is correct and expected.  The gate is
    :func:`create_case_manager_gated_tree` (BTND-07-005), so a broadcast that
    fails *at* the CASE_MANAGER propagates rather than reading as a skip
    (BT-14-001).
    """
    root = py_trees.composites.Sequence(
        name="UpdateCaseBT",
        memory=False,
        children=[
            CheckCaseUpdateOwnerNode(
                case_id=case_id, sender_actor_id=request.actor_id
            ),
            CaptureCaseUpdateBroadcastExclusionsNode(case_id=case_id),
            ApplyCaseUpdateNode(case_id=case_id, request=request),
            create_case_manager_gated_tree(
                name="GuardedBroadcastCaseUpdateBT",
                case_id=case_id,
                children=[BroadcastCaseUpdateNode(case_id=case_id)],
            ),
        ],
    )
    logger.info(
        "Created UpdateCaseBT for case=%s, actor=%s", case_id, actor_id
    )
    return root
