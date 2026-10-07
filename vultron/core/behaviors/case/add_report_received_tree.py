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

"""Received-side BT factory for ``Add(VulnerabilityReport, Case)``.

Only the CASE_MANAGER attaches the report to ``case.vulnerability_reports`` and
commits the canonical ledger entry; every other participant learns of the report
from the entry's ``Announce`` fan-out, applied by
``ApplyOfferReportFromLedgerNode`` (SYNC-02-002, RSH-08-004).  Sender
entitlement is the Case Owner at the manager (CM-30-002, ADR-0115).
"""

import py_trees

from vultron.core.behaviors.case.nodes.reference_list import (
    AttachReportToCaseNode,
    CaseReferenceEditPendingNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
    create_role_scoped_sender_guard,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import SenderIsCaseOwnerNode


def create_add_report_to_case_received_tree(
    report_id: str,
    case_id: str,
    sender_id: str,
) -> py_trees.composites.Sequence:
    """Single-BT received-side tree for ``Add(Report, Case)`` (ADR-0111).

    Structure (the CLP-10-010 stages)::

        GuardedAttachReportAndCommitBT (Sequence)
        ├── IntakeReceivedActivityNode                    # intake
        ├── AddReportSenderGuard (Selector)               # sender guard
        ├── CaseReferenceEditPendingNode                  # duplicate guard
        ├── GuardedCommitCaseLedgerEntryBT (Selector)     # commit
        └── GuardedAttachReportBT (Selector)              # effect

    A report the case already lists fails the duplicate guard before anything
    is committed, so a re-delivery ledgers nothing; the handler reports it as
    ``SKIPPED``.

    Args:
        report_id: ID of the report being added.
        case_id: ID of the case receiving the report.
        sender_id: The activity's sender.
    """
    return create_receive_activity_tree(
        name="GuardedAttachReportAndCommitBT",
        case_id=case_id,
        sender_guard=create_role_scoped_sender_guard(
            name="AddReportSenderGuard",
            case_id=case_id,
            at_case_manager=SenderIsCaseOwnerNode(
                sender_actor_id=sender_id, case_id=case_id
            ),
        ),
        precondition_guards=[
            CaseReferenceEditPendingNode(
                ref_id=report_id,
                case_id=case_id,
                field="vulnerability_reports",
                attach=True,
            )
        ],
        effect_nodes=[
            create_case_manager_gated_tree(
                name="GuardedAttachReportBT",
                case_id=case_id,
                children=[
                    AttachReportToCaseNode(
                        report_id=report_id, case_id=case_id
                    )
                ],
            )
        ],
    )
