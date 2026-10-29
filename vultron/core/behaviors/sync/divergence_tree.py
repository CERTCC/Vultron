#!/usr/bin/env python
#
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
"""Behavior tree for the CASE_MANAGER's answer to a case-diverged fault.

A replica that refuses a copied entry extending its chain sends the
CASE_MANAGER ``Create(ProcessingFault)`` of class
``LedgerEntryRefused/CaseDiverged`` (SYNC-16-001).  The tree here answers it
with a fresh case copy (SYNC-16-003, ADR-0142).
"""

from datetime import datetime

import py_trees

from vultron.core.behaviors.case.intake_only_received_tree import (
    create_intake_only_received_tree,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sync.nodes.reseed import (
    ReportRepeatDivergenceNode,
    ReseedPeerNode,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry

__all__ = ["RESEED_GATE_NAME", "create_case_diverged_fault_tree"]

#: Name of the CASE_MANAGER gate around the tree's re-seed.
RESEED_GATE_NAME = "ReseedIfCaseManager"


def create_case_diverged_fault_tree(
    refused_entry: CaseLedgerEntry | None,
    *,
    sender_id: str,
    sender_rule: SenderRule,
    fault_published: datetime | None,
) -> py_trees.composites.Sequence:
    """Create the BT that re-seeds a replica reporting its case diverged.

    *refused_entry* is the entry the fault's ``inReplyTo`` ``Announce``
    carried; its case is the case the fault concerns.  ``None`` when the
    fault names no ``Announce(CaseLedgerEntry)`` this store sent: there is no
    case to answer for, so the tree only archives the fault and the handler
    refuses it.  At that case's
    CASE_MANAGER the tree logs a divergence the last re-seed's copy already
    reflected, at ERROR once the peer acknowledged that copy's position and at
    WARNING before, or when the fault's claimed time is at or before that
    acknowledgement's (:class:`ReportRepeatDivergenceNode`, SYNC-16-008),
    then sends the sender ``Announce(VulnerabilityCase)`` of its current
    case, rate-bounded per peer (:class:`ReseedPeerNode`, SYNC-16-003,
    SYNC-16-004).  Both are the CASE_MANAGER's own acts, so they sit in
    ``manager_effects`` (BT-17-008); any other receiver does nothing.

    The sender guard is composed from the use case's declared rule on the
    entry's case, so a sender that is not an active participant is refused
    before anything is recorded or sent (SYNC-16-003, HP-01-007).  Nothing is
    committed: the fault is replication signalling (SYNC-16-002).  The tree
    keeps the post-close boundary: once the case is fully closed the fault is
    dropped like any other activity, since CM-23-013 lets only the ledger
    replay keep serving.

    Args:
        refused_entry: The ``CaseLedgerEntry`` the replica refused, or
            ``None`` when the fault names none this store sent.
        sender_id: The fault's ``actor``: the replica to re-seed.
        sender_rule: The use case's declared sender rule (HP-01-008).
        fault_published: The ``published`` time the fault's sender claims,
            or ``None`` when it claims none (SYNC-16-008).
    """
    if refused_entry is None:
        return create_intake_only_received_tree("CaseDivergedFaultReceivedBT")
    case_id = refused_entry.case_id
    return create_receive_activity_tree(
        name="CaseDivergedFaultReceivedBT",
        case_id=None,
        precondition_guards=[],
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id, case_id=case_id
        ),
        manager_effects=[
            ReportRepeatDivergenceNode(
                case_id=case_id,
                peer_id=sender_id,
                refused_entry=refused_entry,
                fault_published=fault_published,
            ),
            ReseedPeerNode(case_id=case_id, peer_id=sender_id),
        ],
        manager_case_id=case_id,
        manager_gate_name=RESEED_GATE_NAME,
    )
