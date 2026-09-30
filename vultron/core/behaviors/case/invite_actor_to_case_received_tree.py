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

"""Received-side BT factories for the InviteActorToCase workflow.

See CLP-10-001, CLP-10-006; Issue #1293.
"""

import logging

import py_trees

from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)

logger = logging.getLogger(__name__)


def create_reject_invite_actor_to_case_received_tree(
    case_id: str,
) -> py_trees.composites.Sequence:
    """Received-side BT for ``Reject(Invite(actor, case))`` on the CaseActor inbox.

    Commits the canonical ``CaseLedgerEntry`` for the invite rejection when the
    receiving actor holds ``CVDRole.CASE_MANAGER`` (CLP-10-006).  No additional
    effect nodes are required: the rejection is self-contained — the CaseActor
    simply records that the invitee declined.

    Args:
        case_id: ID of the VulnerabilityCase referenced by the invite.

    Returns:
        Root ``RejectInviteActorToCaseReceivedBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="RejectInviteActorToCaseReceivedBT",
        case_id=case_id if case_id else None,
        precondition_guards=[],
        effect_nodes=[],
    )


def create_invite_actor_to_case_received_tree(
    case_id: str,
) -> py_trees.composites.Sequence:
    """Received-side BT for ``Invite(Actor, Case)`` on the CaseActor inbox.

    Intake stores the Invite activity as received (CLP-10-017), then the
    canonical ``CaseLedgerEntry`` for the invite is committed when the
    receiving actor holds ``CVDRole.CASE_MANAGER`` (CLP-10-006).  The tree
    has no effect nodes of its own: the per-tree ``StoreActivityNode`` it once
    carried duplicated intake and was removed (CLP-10-019).

    Args:
        case_id: ID of the VulnerabilityCase referenced by the invite.

    Returns:
        Root ``InviteActorToCaseReceivedBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="InviteActorToCaseReceivedBT",
        case_id=case_id if case_id else None,
        precondition_guards=[],
        effect_nodes=[],
    )
