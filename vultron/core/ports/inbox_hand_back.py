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

"""Driven port that hands a buffered ledger entry back to the actor's inbox.

A buffered ``CaseLedgerEntry`` that a commit or a case seed makes appliable is
a delivery of its own (SYNC-14-009, ADR-0135): core does not run its tree
inside the delivery that made it appliable, it hands the entry back to the
receiving actor's own inbox processing through this port.  The adapter wraps
the entry in an ``Announce(CaseLedgerEntry)`` attributed to the case's
CASE_MANAGER and schedules it through the inbox's sole entry point,
``process_payload`` (IO-02-003), so the drain runs the same path as in-order
delivery by construction (SYNC-14-008).

See also:
    - ``vultron/adapters/driven/inbox_hand_back_adapter.py`` — adapter
    - ``vultron/core/behaviors/sync/nodes/hand_back.py`` — the node that calls it
"""

from typing import Protocol

from vultron.core.models.case_ledger_entry import CaseLedgerEntry


class InboxHandBackPort(Protocol):
    """Driven port: give a buffered ledger entry back to this actor's inbox."""

    def hand_back_ledger_entry(
        self,
        entry: CaseLedgerEntry,
        case_manager_id: str,
        receiving_actor_id: str,
    ) -> None:
        """Schedule *entry* as an inbox delivery of its own.

        The adapter wraps *entry* in an ``Announce(CaseLedgerEntry)`` whose
        ``actor`` is *case_manager_id* and whose sole recipient is
        *receiving_actor_id*, then queues it for the receiving actor's inbox
        processing.  It does not process the delivery itself: the delivery
        runs after the one that called this method has finished.

        Args:
            entry: The buffered entry that now extends the local chain tail.
            case_manager_id: The case's CASE_MANAGER, the sender a replica
                applies ledger entries from (SYNC-15, SYNC-13-006).
            receiving_actor_id: The actor whose inbox receives the delivery.
        """
        ...


__all__ = ["InboxHandBackPort"]
