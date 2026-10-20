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

"""Received-side BT factory for OfferCaseParticipantRole (ADR-0039, CM-33).

Builds the tree for ``Offer(CaseParticipantRole, target=Actor,
context=VulnerabilityCase)``.  The Offer reaches two stores.  At the case's
CASE_MANAGER it is the Case Owner's own Offer: the CASE_MANAGER checks it,
commits it and forwards it to the target (CM-33-001 to CM-33-003).  At the
target it is the CASE_MANAGER's forward: the target answers it, to the
CASE_MANAGER (CM-33-004).  The CASE_MANAGER never answers for the target and
never grants the role on the Offer: the grant is the committed Accept
(CM-02-016, CM-33-006).

Structure::

    OfferCaseParticipantRoleReceivedBT (Sequence)
    ├── IntakeReceivedActivityNode           # archives the Offer (CLP-10-017)
    ├── CaseOpenToExternalWrites
    ├── SenderRuleGuard                      # Case Owner at the CM, the CM at
    │                                        # a participant (CM-33-002, -004)
    ├── RoleOfferAdmissibleNode              # CM-33-003
    ├── GuardedCommit                        # CASE_MANAGER only
    ├── AnswerRoleOfferOnReplica (participant replica gate)
    │   ├── IsRoleOfferTargetNode
    │   └── AcceptOrReject (Selector)
    │       ├── AutoAcceptCaseParticipantRoleNode
    │       └── EmitRejectCaseParticipantRoleNode
    └── ForwardRoleOfferToTargetCMGated (CASE_MANAGER gate)
        └── ForwardRoleOfferToTargetNode

See SE-08-003, ADR-0039.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.delegation import (
    AutoAcceptCaseParticipantRoleNode,
    EmitRejectCaseParticipantRoleNode,
    ForwardRoleOfferToTargetNode,
    IsRoleOfferTargetNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_participant_replica_gated_tree,
)
from vultron.core.behaviors.case.nodes.role_offer_guard import (
    RoleOfferAdmissibleNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.replica_emit_exemptions import OFFER_ROLE
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import SenderCheckContext
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


def create_offer_case_participant_role_received_tree(
    offer_id: str,
    case_id: str | None,
    role: CVDRole | None,
    target_actor_id: str | None,
    sender_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Received-side BT factory for OfferCaseParticipantRole (ADR-0039).

    Intake archives the incoming Offer as received (CLP-10-017).  The sender
    guard, composed from *sender_rule*, admits the Case Owner at the
    CASE_MANAGER and the CASE_MANAGER at any other store, and refuses a
    store that does not hold the case (CM-33-002, CM-33-004, PCR-03-001).
    :class:`RoleOfferAdmissibleNode` then refuses an Offer the CASE_MANAGER
    may not record (CM-33-003), so a refused Offer leaves no entry and sends
    nothing.  At the CASE_MANAGER the guarded commit records the Offer and
    the gated :class:`ForwardRoleOfferToTargetNode` sends it on to the target.
    The commit records the received Offer, so it precedes the forward
    (CLP-10-006); the forward is not ledgered on its own, so SYNC-09-002's
    send-then-commit order binds nothing here.  A redelivery of a recorded
    Offer whose forward is not stored reuses its entry and builds the
    forward, so a forward that failed after the commit is sent then; once
    the forward is stored, a redelivery sends nothing (HP-01-003,
    OX-06-002).  At a
    participant replica only the target answers (CM-33-004, BT-17-008).

    Args:
        offer_id: ID of the received ``Offer(CaseParticipantRole)``; the
            recorded Offer's id the forward names in ``in_reply_to``.
        case_id: ID of the VulnerabilityCase context; ``None`` for an Offer
            that names no case, which intake archives and nothing else
            touches (CLP-10-018); its handler refuses it.
        role: The CVDRole offered; ``None`` when the Offer carries none,
            which is refused, never read as a default (CM-33-003).
        target_actor_id: Actor ID of the target the role is offered to.
        sender_id: The Offer's sender, which the sender guard checks.
        sender_rule: The use case's declared sender rule (HP-01-008).

    Returns:
        Root ``OfferCaseParticipantRoleReceivedBT`` Sequence node.
    """
    if case_id is None:
        return create_receive_activity_tree(
            name="OfferCaseParticipantRoleReceivedBT",
            case_id=None,
            precondition_guards=[],
        )

    sender_context = SenderCheckContext(
        sender_id=sender_id, case_id=case_id, case_manager_required=True
    )
    admissible = RoleOfferAdmissibleNode(
        case_id=case_id,
        offer_id=offer_id,
        role=role,
        target_actor_id=target_actor_id,
    )
    if role is None or not target_actor_id:
        # Nothing to forward or answer: the guard refuses the Offer
        # (CM-33-003), so the tree is the door and the guards.
        return create_receive_activity_tree(
            name="OfferCaseParticipantRoleReceivedBT",
            case_id=case_id,
            sender_rule=sender_rule,
            sender_context=sender_context,
            precondition_guards=[admissible],
        )

    answer = create_participant_replica_gated_tree(
        name="AnswerRoleOfferOnReplica",
        case_id=case_id,
        children=[
            IsRoleOfferTargetNode(target_actor_id=target_actor_id),
            py_trees.composites.Selector(
                name="AcceptOrReject",
                memory=False,
                children=[
                    AutoAcceptCaseParticipantRoleNode(
                        offer_id=offer_id,
                        case_id=case_id,
                        role=role,
                        target_actor_id=target_actor_id,
                        vendor_id=sender_id,
                    ),
                    EmitRejectCaseParticipantRoleNode(
                        offer_id=offer_id,
                        case_id=case_id,
                        role=role,
                        target_actor_id=target_actor_id,
                        vendor_id=sender_id,
                    ),
                ],
            ),
        ],
    )
    forward = ForwardRoleOfferToTargetNode(
        case_id=case_id,
        role=role,
        target_actor_id=target_actor_id,
        offer_id=offer_id,
        owner_id=sender_id,
    )
    return create_receive_activity_tree(
        name="OfferCaseParticipantRoleReceivedBT",
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=sender_context,
        precondition_guards=[admissible],
        replica_effects=[answer],
        replica_emit_exemption=OFFER_ROLE,
        manager_effects=[forward],
        manager_case_id=case_id,
        manager_gate_name="ForwardRoleOfferToTargetCMGated",
    )
