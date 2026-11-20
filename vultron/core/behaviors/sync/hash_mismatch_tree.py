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

from vultron.core.behaviors.act_key_scope import with_act_keys
from vultron.core.behaviors.act_keys import SENDER_ID
from vultron.core.behaviors.case.nodes.received_path import ReceivedPath
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sync.nodes.hash_mismatch import (
    ReportHashMismatchNode,
)
from vultron.core.behaviors.sync.refused_entry_fault_stages import (
    refused_entry_fault_stages,
)

__all__ = ["create_hash_mismatch_fault_tree"]


def create_hash_mismatch_fault_tree(
    *,
    sender_id: str,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Create the BT that reports a replica's hash-mismatch fault.

    The tree has the one shape of every refused-entry fault
    (:mod:`~vultron.core.behaviors.sync.refused_entry_fault_stages`):
    it finds the entry the fault's ``inReplyTo`` ``Add`` carried, and with
    it the case the fault concerns, with a lookup node (BT-25-009), and
    refuses a fault that names no ``Add(CaseLedgerEntry)`` this store sent,
    since there is no case to report on (SYNC-03-008, BT-25-010).  At that
    case's CASE_MANAGER the tree logs the fault at ERROR with a re-check of
    the CASE_MANAGER's own copy of the entry (:class:`ReportHashMismatchNode`,
    SYNC-03-010), in ``manager_effects`` (BT-17-008); any other receiver
    does nothing.

    The sender guard is composed from the use case's declared rule on the
    entry's case, so a sender that is not an active participant is refused
    before anything is logged as its report (SYNC-03-008, HP-01-007).
    Nothing is committed, sent, re-seeded or recorded: neither a replay nor a
    re-seed can heal a hash mismatch, and the replay cooldown alone bounds
    the loop it leaves (SYNC-16-002, SYNC-15-013).  The tree keeps the
    post-close boundary, as every received tree does (CM-23-013).

    Args:
        sender_id: The fault's ``actor``: the replica that refused it.
        sender_rule: The use case's declared sender rule (HP-01-008).
    """
    stages = refused_entry_fault_stages(
        answer="report on", requirement="SYNC-03-008"
    )
    return create_receive_activity_tree(
        name="HashMismatchFaultReceivedBT",
        case_id=None,
        precondition_guards=[],
        case_lookup=stages.case_lookup,
        # The fault is replication signalling, never ledgered (SYNC-16-002):
        # the case the lookup finds only gates and guards.
        commits_lookup_case=False,
        # The fault answers an Add this store sent, so it reaches the
        # CASE_MANAGER that holds the canonical ledger; a fault is never
        # relayed to a replica, so the path stage refuses one (SYNC-16-002,
        # HP-01-038).  A fault whose entry this store does not hold is on
        # the no-case path, whose empty side admits no sender;
        # ``case_resolution`` refuses it as naming no entry first
        # (BT-25-010, HP-01-041).
        paths={ReceivedPath.CASE_MANAGER, ReceivedPath.NO_CASE},
        case_resolution=stages.case_resolution,
        sender_rule=sender_rule,
        # The guard reads the case the lookup published (BT-25-011).
        sender_context=SenderCheckContext(sender_id=sender_id),
        manager_effects=[
            with_act_keys(ReportHashMismatchNode(), {SENDER_ID: sender_id}),
        ],
        manager_gate_name="ReportIfCaseManager",
    )
