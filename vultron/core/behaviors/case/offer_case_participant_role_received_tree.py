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

"""Received-side BT factory for OfferCaseParticipantRole (ADR-0039).

Builds the response tree for
``Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)``
received by the target Actor.  Auto-accepts the offer and commits a
ledger entry; falls back to an explicit Reject if accept creation fails.

Structure::

    OfferCaseParticipantRoleReceivedBT (Sequence)
    ├── IntakeReceivedActivityNode                  # archives the Offer (CLP-10-017)
    ├── GuardedCommitOrSkip (Selector, only when case_id provided)
    │   ├── SkipIfNotCaseManager (Sequence)
    │   │   └── Inverter(CheckIsCaseManagerNode)
    │   └── CommitCaseLedgerEntryNode
    └── AcceptOrReject (Selector)
        ├── AutoAcceptCaseParticipantRoleNode
        └── EmitRejectCaseParticipantRoleNode

See SE-08-003, ADR-0039.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.delegation import (
    AutoAcceptCaseParticipantRoleNode,
    EmitRejectCaseParticipantRoleNode,
    GrantCaseParticipantRoleNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.replica_emit_exemptions import OFFER_ROLE
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


def create_offer_case_participant_role_received_tree(
    offer_id: str,
    case_id: str,
    role: CVDRole,
    target_actor_id: str,
    vendor_id: str,
) -> py_trees.composites.Sequence:
    """Received-side BT factory for OfferCaseParticipantRole (ADR-0039).

    Intake archives the incoming Offer as received (CLP-10-017); then — when
    the receiving actor holds the offered CVDRole in the case — the tree
    commits the ``offer_case_participant_role`` ``CaseLedgerEntry``.  The
    auto-accept runs after the commit so the canonical ledger entry exists
    before the ``Accept`` is sent to the offering Vendor.  The per-tree
    ``StoreActivityNode`` this tree once carried duplicated intake and was
    removed (CLP-10-019).

    Args:
        offer_id: ID of the ``Offer(CaseParticipantRole)`` activity.
        case_id: ID of the VulnerabilityCase context.
        role: The CVDRole being offered.
        target_actor_id: Actor ID of the target receiving the role offer.
        vendor_id: Actor ID of the offering Vendor (recipient of Accept/Reject).

    Returns:
        Root ``OfferCaseParticipantRoleReceivedBT`` Sequence node.
    """
    accept_or_reject = py_trees.composites.Selector(
        name="AcceptOrReject",
        memory=False,
        children=[
            AutoAcceptCaseParticipantRoleNode(
                offer_id=offer_id,
                case_id=case_id,
                role=role,
                target_actor_id=target_actor_id,
                vendor_id=vendor_id,
            ),
            EmitRejectCaseParticipantRoleNode(
                offer_id=offer_id,
                case_id=case_id,
                role=role,
                target_actor_id=target_actor_id,
                vendor_id=vendor_id,
            ),
        ],
    )

    # The CASE_MANAGER grants the role on its own copy at commit; it excludes
    # itself from the Announce fan-out, so it never replays its own accept
    # entry. Remote replicas apply the grant from the ledger (CM-02-016).
    manager_effects: list[py_trees.behaviour.Behaviour] | None = (
        [
            GrantCaseParticipantRoleNode(
                case_id=case_id,
                role=role,
                target_actor_id=target_actor_id,
            )
        ]
        if case_id
        else None
    )

    return create_receive_activity_tree(
        name="OfferCaseParticipantRoleReceivedBT",
        case_id=case_id if case_id else None,
        precondition_guards=[],
        replica_effects=[accept_or_reject],
        replica_emit_exemption=OFFER_ROLE,
        manager_effects=manager_effects,
        manager_case_id=case_id if case_id else None,
    )
