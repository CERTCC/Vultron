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

See CLP-10-001, CLP-10-005, CLP-10-006; Issue #1293, #3821.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.invite_received import (
    LogInviteReceivedNode,
    RecordInviteTrustAnchorNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_participant_replica_gated_tree,
)
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
    invitee_id: str,
    inviter_id: str,
) -> py_trees.composites.Sequence:
    """Received-side BT for ``Invite(Actor, CaseStub)`` — one tree for every receiver.

    The CASE_MANAGER emits the Invite from its own store and commits it in
    the emitting tree; it never receives its own Invite (CM-17-006,
    ADR-0109).  The receiver is therefore the invitee, which holds only the
    Invite's case stub (MV-10-004)::

        InviteActorToCaseReceivedBT (Sequence)
        ├── Intake                       # stores the Invite idempotently
        ├── GuardedCommitCaseLedgerEntryBT   # CASE_MANAGER only — skips here
        └── InviteeRecordsInvite         # not the CASE_MANAGER
            ├── LogInviteReceivedNode        # SL-04-006
            └── RecordInviteTrustAnchorNode  # PCR-03-004

    Both gates read a case the receiver does not hold as "not the
    CASE_MANAGER" (``case_may_be_absent``), because an invitee has no replica
    until the case is announced.

    Args:
        case_id: ID of the case the Invite's stub names (its ``target``).
        invitee_id: The invited actor (the Invite's ``object``).
        inviter_id: The Invite's sender, recorded as the case's expected
            CASE_MANAGER.

    Returns:
        Root ``InviteActorToCaseReceivedBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="InviteActorToCaseReceivedBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[
            create_participant_replica_gated_tree(
                name="InviteeRecordsInvite",
                case_id=case_id,
                children=[
                    LogInviteReceivedNode(
                        invitee_id=invitee_id,
                        case_id=case_id,
                        sender_id=inviter_id,
                    ),
                    RecordInviteTrustAnchorNode(
                        case_id=case_id,
                        invitee_id=invitee_id,
                        case_actor_id=inviter_id,
                    ),
                ],
                case_may_be_absent=True,
            ),
        ],
        case_may_be_absent=True,
    )
