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

"""Received-side BT factory for the OfferCaseManagerRole workflow (ADR-0022).

See DEMOMA-08-002, DEMOMA-08-003; Issue #469, Issue #1021.
"""

import logging
from typing import Any

import py_trees

from vultron.core.behaviors.case.nodes.delegation import (
    AutoAcceptCaseManagerRoleNode,
    EmitRejectCaseManagerRoleNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.report.nodes.storage import StoreActivityNode

logger = logging.getLogger(__name__)


def create_offer_case_manager_role_received_tree(
    offer_id: str,
    offer_obj: Any,
    case_id: str,
    participant_id: str,
    vendor_id: str,
) -> py_trees.composites.Sequence:
    """Single-BT received-side tree for OfferCaseManagerRole (ADR-0022).

    Idempotently stores the incoming Offer, then — when the receiving actor
    holds ``CVDRole.CASE_MANAGER`` — commits the initialization
    ``CaseLedgerEntry`` that back-fills the canonical record
    (DEMOMA-08-002, DEMOMA-08-003).  The guarded commit runs BEFORE the
    auto-accept so the canonical ledger entry for the Offer exists before
    the ``Accept`` is sent to the offering Vendor.

    Finally, the tree attempts to auto-accept the offer by emitting
    ``Accept(Offer(CaseManagerRole))`` to the offering Vendor.  If the
    Accept activity *creation* fails (e.g. ``trigger_activity_factory``
    unavailable or a factory-level error) before any state is written, the
    ``AcceptOrReject`` Selector falls back to
    :class:`~vultron.core.behaviors.case.nodes.delegation.EmitRejectCaseManagerRoleNode`
    which sends an explicit ``Reject`` so the Vendor is informed rather
    than receiving silence.

    Outbox-enqueue failures that occur *after* the Accept activity has been
    persisted are **not** converted to Reject: the exception propagates from
    the node so BTBridge fails the tree hard, preserving the persisted
    Accept without emitting a contradictory Reject.  This distinction is
    enforced by :class:`~vultron.core.behaviors.case.nodes.delegation.AutoAcceptCaseManagerRoleNode`
    which splits the two operations into separate error paths.

    Structure::

        OfferCaseManagerRoleReceivedBT (Sequence)
        ├── GuardedCommitOrSkip (Selector, only when case_id provided)
        │   ├── Sequence                              # Record receipt (CLP-10-006)
        │   │   ├── CheckIsCaseManagerNode
        │   │   └── CommitCaseLedgerEntryNode
        │   └── Success("CommitSkippedNotCaseManager")
        ├── StoreActivityNode("OfferCaseManagerRole")
        └── AcceptOrReject (Selector)
            ├── AutoAcceptCaseManagerRoleNode
            └── EmitRejectCaseManagerRoleNode

    Args:
        offer_id: ID of the ``Offer(CaseManagerRole)`` activity.
        offer_obj: The wire activity object to persist idempotently.
        case_id: ID of the VulnerabilityCase referenced by the offer.
        participant_id: ID of the CaseParticipant being offered the role.
        vendor_id: Actor ID of the offering Vendor (recipient of Accept/Reject).

    Returns:
        Root ``OfferCaseManagerRoleReceivedBT`` Sequence node.
    """
    accept_or_reject = py_trees.composites.Selector(
        name="AcceptOrReject",
        memory=False,
        children=[
            AutoAcceptCaseManagerRoleNode(
                offer_id=offer_id,
                case_id=case_id,
                participant_id=participant_id,
                vendor_id=vendor_id,
            ),
            EmitRejectCaseManagerRoleNode(
                offer_id=offer_id,
                case_id=case_id,
                participant_id=participant_id,
                vendor_id=vendor_id,
            ),
        ],
    )
    return create_receive_activity_tree(
        name="OfferCaseManagerRoleReceivedBT",
        case_id=case_id if case_id else None,
        precondition_guards=[],
        effect_nodes=[
            StoreActivityNode(
                activity_id=offer_id,
                activity_obj=offer_obj,
                label="OfferCaseManagerRole",
            ),
            accept_or_reject,
        ],
    )
