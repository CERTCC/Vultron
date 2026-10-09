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

See CM-11-010, CM-11-011, CM-11-012, ADR-0121, RSH-06-006.
"""

import py_trees

from vultron.core.behaviors.case.nodes.full_case_invite import (
    CheckFullCaseReplyNode,
    LogFullCaseInviteReceivedNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_participant_replica_gated_tree,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.report.rm_declaration_tree import (
    record_rm_declaration,
    rm_declaration_guard,
    rm_gap_note,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderIsCaseManagerNode,
    SenderIsInviteeNode,
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
    (SL-04-006).

    The sender must be the case's CASE_MANAGER: the replica's, else the one
    recorded as the trust anchor from the stub Invite, else the Invite is
    refused (``anchored``, PCR-03-004, HP-01-006, ADR-0115)::

        InviteActorToFullCaseReceivedBT (Sequence)
        ├── Intake
        ├── SenderIsCaseManagerNode          # anchored; refuses any other sender
        ├── GuardedCommitCaseLedgerEntryBT   # CASE_MANAGER only — skips here
        └── InviteeRecordsFullCaseInvite     # not the CASE_MANAGER
            └── LogFullCaseInviteReceivedNode
    """
    return create_receive_activity_tree(
        name="InviteActorToFullCaseReceivedBT",
        case_id=case_id,
        sender_guard=SenderIsCaseManagerNode(case_id=case_id, anchored=True),
        precondition_guards=[],
        replica_effects=[
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

    The sender must be the invitee of the Invite this store recorded
    (CM-11-017, HP-01-006, ADR-0115).
    The CASE_MANAGER checks the reply's ledger position against the Invite's
    floor before it commits anything (CM-11-012), adjudicates the RM
    declaration with the shared rule (RSH-06-006), commits the receipt, then
    records the participant's RM state via the idempotent DECLARATION write
    and posts a gap note when the move was non-adjacent (RSH-06-001,
    RSH-06-004)::

        <name> (Sequence)
        ├── Intake
        ├── SenderIsInviteeNode              # sender is the recorded invitee
        ├── CheckFullCaseReplyNode           # position / participant checks
        ├── AdjudicateRMDeclarationNode      # shared rule (RSH-06-006)
        ├── GuardedCommitCaseLedgerEntryBT
        └── FullCaseReplyEffects             # CASE_MANAGER only
            ├── Idempotent<name> (Selector)  # already recorded → skip
            └── EmitRMGapNote               # gap note when anomalous

    The guards sit in the factory's ``PreconditionGuardStage``: when the
    adjudication refuses a regression, its refusal-effects stage posts the
    same note at the CASE_MANAGER before the tree fails (CLP-10-022).
    """
    return create_receive_activity_tree(
        name=name,
        case_id=case_id,
        sender_guard=SenderIsInviteeNode(
            invite_id=invite_id, sender_actor_id=replier_id, case_id=case_id
        ),
        precondition_guards=[
            CheckFullCaseReplyNode(
                case_id=case_id,
                invite_id=invite_id,
                replier_id=replier_id,
                position=position,
            ),
            rm_declaration_guard(replier_id, rm_state, case_id),
        ],
        manager_effects=record_rm_declaration(
            sender_actor_id=replier_id,
            declared_rm=rm_state,
            case_id=case_id,
            name=f"TransitionRMto{rm_state.name.title()}",
        ),
        manager_case_id=case_id,
        manager_gate_name="FullCaseReplyEffects",
        refusal_effects=[rm_gap_note(replier_id, case_id)],
    )
