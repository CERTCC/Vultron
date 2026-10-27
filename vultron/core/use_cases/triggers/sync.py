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
"""Trigger helper for LedgerReconciliation: a participant states its positions.

Public entry point:

- :func:`state_ledger_positions_trigger`

Spec: SYNC-17-001, SYNC-17-007.

Note: ``commit_log_entry_trigger`` was removed (BT-06-006), and so was
``replay_missing_entries_trigger``, whose only caller was a test: a replay is
the CASE_MANAGER's answer to a ``Reject`` or a ``Read(CaseLedgerEntry)``, run
by ``ReplayMissingEntriesNode`` in the received tree (SYNC-03-002,
SYNC-17-004).
"""

from __future__ import annotations

import logging

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.state_positions_tree import (
    create_state_ledger_positions_tree,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.errors import VultronBTInternalError

logger = logging.getLogger(__name__)


def state_ledger_positions_trigger(
    dl: CaseOutboxPersistence,
    actor_id: str,
    sync_port: SyncActivityPort,
) -> int:
    """Queue ``Read(CaseLedgerEntry)`` for each case replica *actor_id* holds.

    Each names the tail of the actor's replica and goes to the case's
    CASE_MANAGER, so a participant that missed the last entry before a quiet
    period is caught up without waiting for a new commit (SYNC-17-001,
    SYNC-17-007, ADR-0155).  The reference participant runs it after a
    restart and, when configured, on an interval.  The work runs in one
    behavior tree (SBT-01-001); the queued activities go out by the outbox.

    Args:
        dl: The actor's own store; its outbox receives the statements.
        actor_id: The participant stating its positions.
        sync_port: Builds and queues each ``Read(CaseLedgerEntry)``.

    Returns:
        The number of statements queued.

    Raises:
        VultronBTInternalError: The tree failed.
    """
    tree = create_state_ledger_positions_tree()
    result = BTBridge(datalayer=dl, sync_port=sync_port).execute_with_setup(
        tree=tree, actor_id=actor_id
    )
    if result.status != Status.SUCCESS:
        raise VultronBTInternalError(
            f"StateLedgerPositionsBT: {result.feedback_message}"
        )
    logger.info(
        "sync: actor '%s' stated its ledger position for %d case(s)"
        " (SYNC-17-007)",
        actor_id,
        tree.sent,
    )
    return tree.sent
