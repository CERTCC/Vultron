#!/usr/bin/env python
"""Behavior tree factory for a participant's ledger position statements.

The participant states, for each case replica it holds, the last ledger entry
it has applied, as ``Read(CaseLedgerEntry)`` to the case's CASE_MANAGER
(SYNC-17-001, SYNC-17-007, ADR-0155).  The CASE_MANAGER's answer is
``read_tree``'s.
"""

from vultron.core.behaviors.sync.nodes import StateLedgerPositionsNode


def create_state_ledger_positions_tree() -> StateLedgerPositionsNode:
    """Create the BT that states the executing actor's ledger positions.

    One ``Read(CaseLedgerEntry)`` per case replica the actor holds, each
    naming its replica's tail, to the case's CASE_MANAGER.  The tree is the
    single node that does it; the caller reads its ``sent`` count.
    """
    return StateLedgerPositionsNode(name="StateLedgerPositions")


__all__ = ["create_state_ledger_positions_tree"]
