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
from vultron.core.behaviors.case.nodes.invite_reject_participant import (
    ApplyInviteRejectToParticipantNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_participant_replica_gated_tree,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import SenderCheckContext

logger = logging.getLogger(__name__)


def create_reject_invite_actor_to_case_received_tree(
    case_id: str,
    invite_id: str,
    invitee_id: str | None = None,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Received-side BT for ``Reject(Invite(actor, case))`` on the CaseActor inbox.

    Commits the canonical ``CaseLedgerEntry`` for the invite rejection when the
    receiving actor holds ``CVDRole.CASE_MANAGER`` (CLP-10-006).  When
    ``invitee_id`` is supplied, also applies the reject effects to the inert
    participant record: RM ``CLOSED``, VF ``Vf``, PEC ``DECLINED`` (when an
    embargo is in force) — AC-3 (CM-11-007, CM-11-009, ADR-0114).

    The sender must be the invitee of the stub Invite this store recorded for
    the case, or the Reject is refused before anything is written (CM-11-017,
    HP-01-006, ADR-0115).  The factory composes that guard from the use
    case's declared rule (HP-01-008); the handler refuses a Reject that names
    no case before it builds this tree, so the rule needs no side for an
    activity outside any case.

    Args:
        case_id: ID of the VulnerabilityCase referenced by the invite; never
            empty.
        invitee_id: Actor ID of the rejecting invitee (the reply's sender).
            Required for AC-3 effects; omit only when the invitee cannot be
            resolved, in which case the sender guard refuses.
        invite_id: ID of the recorded stub Invite the Reject answers.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).

    Returns:
        Root ``RejectInviteActorToCaseReceivedBT`` Sequence node.
    """
    manager_effects: list[py_trees.behaviour.Behaviour] = []
    if invitee_id:
        manager_effects.append(
            ApplyInviteRejectToParticipantNode(
                case_id=case_id,
                invitee_id=invitee_id,
            )
        )

    return create_receive_activity_tree(
        name="RejectInviteActorToCaseReceivedBT",
        case_id=case_id,
        precondition_guards=[],
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=invitee_id or "",
            case_id=case_id,
            invite_id=invite_id,
            invite_is_case_join=True,
        ),
        manager_effects=manager_effects,
        manager_case_id=case_id if manager_effects else None,
        manager_gate_name=(
            "RejectInviteApplyEffects" if manager_effects else None
        ),
    )


def create_invite_actor_to_case_received_tree(
    case_id: str,
    invitee_id: str,
    inviter_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Received-side BT for ``Invite(Actor, CaseStub)`` — one tree for every receiver.

    The CASE_MANAGER emits the Invite from its own store and commits it in
    the emitting tree; it never receives its own Invite (CM-17-006,
    ADR-0109).  The receiver is therefore the invitee, which holds only the
    Invite's case stub (MV-10-004)::

        InviteActorToCaseReceivedBT (Sequence)
        ├── Intake                       # stores the Invite idempotently
        ├── CaseOpenToExternalWrites     # post-close boundary (CM-23-013)
        ├── <sender guard>               # composed from the declared rule
        ├── ClockDecisions               # CASE_MANAGER only — skips here
        ├── GuardedCommitCaseLedgerEntryBT   # CASE_MANAGER only — skips here
        └── InviteeRecordsInvite         # not the CASE_MANAGER
            ├── LogInviteReceivedNode        # SL-04-006
            └── RecordInviteTrustAnchorNode  # PCR-03-004

    Both gates read a case the receiver does not hold as "not the
    CASE_MANAGER" (``case_may_be_absent``), because an invitee has no replica
    until the case is announced.

    The factory composes the sender guard from the use case's declared rule
    (HP-01-008): the sender must be the case's CASE_MANAGER, which alone
    issues the Invite (CM-17-006, PCR-03-001).  An invitee holding only the
    stub has no CASE_MANAGER to compare against, so the guard passes there
    (the bootstrap window) and the trust-anchor rules of PCR-03-004 decide
    what the Invite may record.

    Args:
        case_id: ID of the case the Invite's stub names (its ``target``).
        invitee_id: The invited actor (the Invite's ``object``).
        inviter_id: The Invite's sender, recorded as the case's expected
            CASE_MANAGER.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).

    Returns:
        Root ``InviteActorToCaseReceivedBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="InviteActorToCaseReceivedBT",
        case_id=case_id,
        precondition_guards=[],
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=inviter_id, case_id=case_id
        ),
        replica_effects=[
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
