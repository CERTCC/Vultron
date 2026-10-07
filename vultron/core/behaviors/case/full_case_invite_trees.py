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

"""Received-side BT factories for the full-case Invite and its replies.

See CM-11-010, CM-11-011, CM-11-012, ADR-0121.
"""

import py_trees

from vultron.core.behaviors.case.nodes.full_case_invite import (
    ApplyFullCaseReplyToParticipantNode,
    CheckFullCaseReplyNode,
    LogFullCaseInviteReceivedNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
    create_participant_replica_gated_tree,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.states.rm import RM


def create_invite_actor_to_full_case_received_tree(
    case_id: str,
    invitee_id: str,
    inviter_id: str,
    floor: LedgerPosition,
) -> py_trees.composites.Sequence:
    """Received-side BT for the full-case ``Invite(Actor)[target=Case]``.

    The CASE_MANAGER commits the Invite in the tree that emits it and never
    receives its own Invite (ADR-0109), so the receiver is the invitee.  It
    holds the case from the Announce, so the Invite needs no record beyond the
    archive that intake writes (CLP-10-017); the tree logs the receipt
    (SL-04-006)::

        InviteActorToFullCaseReceivedBT (Sequence)
        ├── Intake
        ├── GuardedCommitCaseLedgerEntryBT   # CASE_MANAGER only — skips here
        └── InviteeRecordsFullCaseInvite     # not the CASE_MANAGER
            └── LogFullCaseInviteReceivedNode
    """
    return create_receive_activity_tree(
        name="InviteActorToFullCaseReceivedBT",
        case_id=case_id,
        precondition_guards=[],
        effect_nodes=[
            create_participant_replica_gated_tree(
                name="InviteeRecordsFullCaseInvite",
                case_id=case_id,
                children=[
                    LogFullCaseInviteReceivedNode(
                        invitee_id=invitee_id,
                        case_id=case_id,
                        sender_id=inviter_id,
                        floor=floor,
                    )
                ],
                case_may_be_absent=True,
            ),
        ],
        case_may_be_absent=True,
    )


def create_full_case_invite_reply_received_tree(
    name: str,
    case_id: str,
    invite_id: str,
    replier_id: str,
    position: LedgerPosition,
    rm_state: RM,
) -> py_trees.composites.Sequence:
    """Received-side BT for a reply to the full-case Invite.

    The CASE_MANAGER checks the reply's ledger position against the Invite's
    floor before it commits anything (CM-11-012), commits the receipt, then
    records the participant's RM transition (CM-11-011)::

        <name> (Sequence)
        ├── Intake
        ├── CheckFullCaseReplyNode           # judges only as the CASE_MANAGER
        ├── GuardedCommitCaseLedgerEntryBT
        └── FullCaseReplyEffects             # CASE_MANAGER only
            └── ApplyFullCaseReplyToParticipantNode
    """
    return create_receive_activity_tree(
        name=name,
        case_id=case_id,
        precondition_guards=[
            CheckFullCaseReplyNode(
                case_id=case_id,
                invite_id=invite_id,
                replier_id=replier_id,
                position=position,
            )
        ],
        effect_nodes=[
            create_case_manager_gated_tree(
                name="FullCaseReplyEffects",
                case_id=case_id,
                children=[
                    ApplyFullCaseReplyToParticipantNode(
                        case_id=case_id,
                        replier_id=replier_id,
                        rm_state=rm_state,
                    )
                ],
            )
        ],
    )
