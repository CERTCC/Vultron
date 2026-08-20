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
    ├── GuardedCommitOrSkip (Selector, only when case_id provided)
    │   ├── SkipIfNotCaseManager (Sequence)
    │   │   └── Inverter(CheckIsCaseManagerNode)
    │   └── CommitCaseLedgerEntryNode
    ├── StoreActivityNode("OfferCaseParticipantRole")
    └── AcceptOrReject (Selector)
        ├── AutoAcceptCaseParticipantRoleNode
        └── EmitRejectCaseParticipantRoleNode

See SE-08-003, ADR-0039.
"""

import logging
from typing import Any

import py_trees

from vultron.core.behaviors.case.nodes.delegation import (
    AutoAcceptCaseParticipantRoleNode,
    EmitRejectCaseParticipantRoleNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.report.nodes.storage import StoreActivityNode
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


def create_offer_case_participant_role_received_tree(
    offer_id: str,
    offer_obj: Any,
    case_id: str,
    role: CVDRole,
    target_actor_id: str,
    vendor_id: str,
) -> py_trees.composites.Sequence:
    """Received-side BT factory for OfferCaseParticipantRole (ADR-0039).

    Idempotently stores the incoming Offer, then — when the receiving actor
    holds the offered CVDRole in the case — commits the
    ``offer_case_participant_role`` ``CaseLedgerEntry``.  The auto-accept
    runs after the commit so the canonical ledger entry exists before the
    ``Accept`` is sent to the offering Vendor.

    Args:
        offer_id: ID of the ``Offer(CaseParticipantRole)`` activity.
        offer_obj: The wire activity object to persist idempotently.
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

    return create_receive_activity_tree(
        name="OfferCaseParticipantRoleReceivedBT",
        case_id=case_id if case_id else None,
        precondition_guards=[],
        effect_nodes=[
            StoreActivityNode(
                activity_id=offer_id,
                activity_obj=offer_obj,
                label="OfferCaseParticipantRole",
            ),
            accept_or_reject,
        ],
    )
