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

from vultron.core.behaviors.case.nodes.communication import (
    AutoAcceptCaseManagerRoleNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    create_guarded_commit_case_ledger_entry_tree,
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

    Finally, the tree auto-accepts the offer by emitting
    ``Accept(Offer(CaseManagerRole))`` to the offering Vendor.  If
    ``trigger_activity_factory`` is unavailable the auto-accept node returns
    ``FAILURE``, which propagates through the Sequence so the caller can log
    the failure.  A protocol-level Reject path is tracked in GitHub.

    Structure::

        OfferCaseManagerRoleReceivedBT (Sequence)
        ├── StoreActivityNode("OfferCaseManagerRole")
        ├── GuardedCommitOrSkip (Selector, only when case_id provided)
        │   ├── Sequence
        │   │   ├── CheckIsCaseManagerNode
        │   │   └── CommitCaseLedgerEntryNode
        │   └── Success("CommitSkippedNotCaseManager")
        └── AutoAcceptCaseManagerRoleNode

    Args:
        offer_id: ID of the ``Offer(CaseManagerRole)`` activity.
        offer_obj: The wire activity object to persist idempotently.
        case_id: ID of the VulnerabilityCase referenced by the offer.
        participant_id: ID of the CaseParticipant being offered the role.
        vendor_id: Actor ID of the offering Vendor (recipient of Accept).

    Returns:
        Root ``OfferCaseManagerRoleReceivedBT`` Sequence node.
    """
    children: list[py_trees.behaviour.Behaviour] = [
        StoreActivityNode(
            activity_id=offer_id,
            activity_obj=offer_obj,
            label="OfferCaseManagerRole",
        ),
    ]

    if case_id:
        children.append(
            create_guarded_commit_case_ledger_entry_tree(case_id=case_id)
        )

    children.append(
        AutoAcceptCaseManagerRoleNode(
            offer_id=offer_id,
            case_id=case_id,
            participant_id=participant_id,
            vendor_id=vendor_id,
        )
    )

    return py_trees.composites.Sequence(
        name="OfferCaseManagerRoleReceivedBT",
        memory=False,
        children=children,
    )
