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

from vultron.core.behaviors.act_key_scope import with_act_keys
from vultron.core.behaviors.act_keys import SENDER_ID
from vultron.core.behaviors.case.nodes.received_path import ReceivedPath
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sync.nodes.reseed import (
    ReportRepeatDivergenceNode,
    ReseedPeerNode,
)
from vultron.core.behaviors.sync.refused_entry_fault_stages import (
    refused_entry_fault_stages,
)

__all__ = ["RESEED_GATE_NAME", "create_case_diverged_fault_tree"]

#: Name of the CASE_MANAGER gate around the tree's re-seed.
RESEED_GATE_NAME = "ReseedIfCaseManager"


def create_case_diverged_fault_tree(
    *,
    sender_id: str,
    sender_rule: SenderRule,
    fault_published: datetime | None,
) -> py_trees.composites.Sequence:
    """Create the BT that re-seeds a replica reporting its case diverged.

    The tree has the one shape of every refused-entry fault
    (:mod:`~vultron.core.behaviors.sync.refused_entry_fault_stages`):
    it finds the entry the fault's ``inReplyTo`` ``Add`` carried, and with
    it the case the fault concerns, with a lookup node (BT-25-009), and
    refuses a fault that names no ``Add(CaseLedgerEntry)`` this store sent,
    since there is no case to re-seed (SYNC-16-003, BT-25-010).  At that
    case's CASE_MANAGER the tree logs a divergence the last re-seed's copy
    already reflected, at ERROR once the peer acknowledged that copy's
    position and at WARNING before, or when the fault's claimed time is at
    or before that acknowledgement's (:class:`ReportRepeatDivergenceNode`,
    SYNC-16-008), then sends the sender ``Announce(VulnerabilityCase)`` of
    its current case, rate-bounded per peer (:class:`ReseedPeerNode`,
    SYNC-16-003, SYNC-16-004).  Both are the CASE_MANAGER's own acts, so
    they sit in ``manager_effects`` (BT-17-008); any other receiver does
    nothing.

    The sender guard is composed from the use case's declared rule on the
    entry's case, so a sender that is not an active participant is refused
    before anything is recorded or sent (SYNC-16-011, HP-01-007); the
    re-seed declares the same refusal should it ever be reached (CM-10-004).
    Nothing is committed: the fault is replication signalling (SYNC-16-002).
    The tree keeps the post-close boundary: once the case is fully closed
    the fault is dropped like any other activity, since CM-23-042 lets only
    the ledger replay keep serving.

    Args:
        sender_id: The fault's ``actor``: the replica to re-seed.
        sender_rule: The use case's declared sender rule (HP-01-008).
        fault_published: The ``published`` time the fault's sender claims,
            or ``None`` when it claims none (SYNC-16-008).
    """
    stages = refused_entry_fault_stages(
        answer="re-seed", requirement="SYNC-16-003"
    )
    return create_receive_activity_tree(
        name="CaseDivergedFaultReceivedBT",
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
            with_act_keys(
                ReportRepeatDivergenceNode(fault_published=fault_published),
                {SENDER_ID: sender_id},
            ),
            with_act_keys(
                ReseedPeerNode(refuses_withheld_peer=True),
                {SENDER_ID: sender_id},
            ),
        ],
        manager_gate_name=RESEED_GATE_NAME,
    )
