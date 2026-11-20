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
"""The stages every received tree answering a refused-entry fault shares.

A replica that refuses a copied entry sends the CASE_MANAGER
``Create(ProcessingFault)`` naming the refused ``Add(CaseLedgerEntry)``
(SYNC-16-001, SYNC-03-007).  The case-diverged and hash-mismatch trees share
everything but their CASE_MANAGER effects, and every fault of either class
runs the same shape whether or not its entry is found (BTND-01-009):

1. :class:`~vultron.core.behaviors.sync.nodes.refused_entry.FindRefusedLedgerEntry`
   publishes the entry, its case and the ``Add``'s id, ahead of the path
   stage (BT-25-009).
2. The path stage reads the receiver's role in that case.  Each tree
   declares the CASE_MANAGER path and the no-case path: a replica is refused
   there (HP-01-005, HP-01-038), and a fault whose entry was not found passes
   on with no case.  A fault carries no case (ASK-07-006), so the inbox
   delivers it without its case being known, which is what HP-01-041 admits
   the no-case declaration for.
3. :class:`~vultron.core.behaviors.sync.nodes.refused_entry.RefusedLedgerEntryFound`
   refuses a fault naming no ``Add(CaseLedgerEntry)`` this actor sent, with a
   declared reason (BT-25-010), before the sender guard, whose no-case side
   admits no sender.
4. The sender guard checks the declared rule on the entry's case
   (HP-01-007), and the CASE_MANAGER's effects run in its gate (BT-17-008).

Nothing is committed: a fault is replication signalling (SYNC-16-002), so
each tree passes ``commits_lookup_case=False`` and the lookup's case only
gates and guards.  Each tree's factory composes these stages through
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
itself, with its own declaration and effects (CLP-10-017).
"""

from typing import NamedTuple

import py_trees

from vultron.core.behaviors.sync.nodes.refused_entry import (
    FindRefusedLedgerEntry,
    RefusedLedgerEntryFound,
)

__all__ = ["RefusedEntryFaultStages", "refused_entry_fault_stages"]


class RefusedEntryFaultStages(NamedTuple):
    """The stages a refused-entry fault's received tree shares."""

    case_lookup: py_trees.behaviour.Behaviour
    case_resolution: list[py_trees.behaviour.Behaviour]


def refused_entry_fault_stages(
    *, answer: str, requirement: str
) -> RefusedEntryFaultStages:
    """The lookup and its miss guard, for a fault's tree.

    The sender guard reads the case the lookup publishes, so each tree's
    ``SenderCheckContext`` names its sender and no case (BT-25-011).

    Args:
        answer: What the tree's answer does for the case, as the miss
            refusal names it (``"re-seed"``).
        requirement: The requirement of that answer, cited by the refusal.
    """
    return RefusedEntryFaultStages(
        case_lookup=FindRefusedLedgerEntry(),
        case_resolution=[
            RefusedLedgerEntryFound(answer=answer, requirement=requirement)
        ],
    )
