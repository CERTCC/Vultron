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

"""Received-side BT factory for the InviteActorToCase workflow.

See CLP-10-001, CLP-10-006; Issue #1293.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.report.nodes.storage import StoreActivityNode

logger = logging.getLogger(__name__)


def create_invite_actor_to_case_received_tree(
    invite_id: str,
    invite_obj: object,
    case_id: str,
) -> py_trees.composites.Sequence:
    """Received-side BT for ``Invite(Actor, Case)`` on the CaseActor inbox.

    Commits the canonical ``CaseLedgerEntry`` for the invite when the
    receiving actor holds ``CVDRole.CASE_MANAGER`` (CLP-10-006), then
    stores the Invite activity idempotently (CLP-10-001).  The tree is
    composed by :func:`create_receive_activity_tree` which enforces the
    ``precondition_guards → GuardedCommitCaseLedgerEntryBT → effect_nodes``
    ordering (CLP-10-006).

    Args:
        invite_id: ID of the ``Invite(Actor, Case)`` activity.
        invite_obj: The wire activity object to persist idempotently.
        case_id: ID of the VulnerabilityCase referenced by the invite.

    Returns:
        Root ``InviteActorToCaseReceivedBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="InviteActorToCaseReceivedBT",
        case_id=case_id if case_id else None,
        precondition_guards=[],
        effect_nodes=[
            StoreActivityNode(
                activity_id=invite_id,
                activity_obj=invite_obj,
                label="InviteActorToCase",
            ),
        ],
    )
