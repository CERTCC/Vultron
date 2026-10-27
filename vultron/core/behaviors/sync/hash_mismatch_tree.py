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
"""Behavior tree for the CASE_MANAGER's answer to a hash-mismatch fault.

A replica that refuses a copied entry whose content does not reproduce its
stated hash sends the CASE_MANAGER ``Create(ProcessingFault)`` of class
``LedgerEntryRefused/HashMismatch`` (SYNC-03-007).  The tree here logs it and
re-checks the CASE_MANAGER's own copy, and changes nothing (SYNC-03-008,
SYNC-03-010).
"""

import py_trees

from vultron.core.behaviors.case.intake_only_received_tree import (
    create_intake_only_received_tree,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sync.nodes.hash_mismatch import (
    ReportHashMismatchNode,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry

__all__ = ["create_hash_mismatch_fault_tree"]


def create_hash_mismatch_fault_tree(
    refused_entry: CaseLedgerEntry | None,
    *,
    announce_id: str | None,
    sender_id: str,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Create the BT that reports a replica's hash-mismatch fault.

    *refused_entry* is the entry the fault's ``inReplyTo`` ``Announce``
    (*announce_id*) carried; its case is the case the fault concerns.
    ``None`` when the fault names no ``Announce(CaseLedgerEntry)`` this store
    sent: there is no case to answer for, so the tree only archives the fault
    and the handler refuses it.  At that case's CASE_MANAGER the tree logs
    the fault at ERROR with a re-check of the CASE_MANAGER's own copy of the
    entry (:class:`ReportHashMismatchNode`, SYNC-03-010), in
    ``manager_effects`` (BT-17-008); any other receiver does nothing.

    The sender guard is composed from the use case's declared rule on the
    entry's case, so a sender that is not an active participant is refused
    before anything is logged as its report (SYNC-03-008, HP-01-007).
    Nothing is committed, sent, re-seeded or recorded: neither a replay nor a
    re-seed can heal a hash mismatch, and the replay cooldown alone bounds
    the loop it leaves (SYNC-16-002, SYNC-15-013).  The tree keeps the
    post-close boundary, as every received tree does (CM-23-013).

    Args:
        refused_entry: The ``CaseLedgerEntry`` the replica refused, or
            ``None`` when the fault names none this store sent.
        announce_id: The fault's ``inReplyTo``: the refused ``Announce``.
        sender_id: The fault's ``actor``: the replica that refused it.
        sender_rule: The use case's declared sender rule (HP-01-008).
    """
    # The use case reads the entry from the Announce *announce_id* names, so
    # an entry never arrives without one; the second test is defensive.
    if refused_entry is None or announce_id is None:
        return create_intake_only_received_tree("HashMismatchFaultReceivedBT")
    case_id = refused_entry.case_id
    return create_receive_activity_tree(
        name="HashMismatchFaultReceivedBT",
        case_id=None,
        precondition_guards=[],
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id, case_id=case_id
        ),
        manager_effects=[
            ReportHashMismatchNode(
                refused_entry, peer_id=sender_id, announce_id=announce_id
            ),
        ],
        manager_case_id=case_id,
        manager_gate_name="ReportIfCaseManager",
    )
