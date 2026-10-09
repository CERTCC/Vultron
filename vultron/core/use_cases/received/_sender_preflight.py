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

"""Run a sender-entitlement guard before a handler's first write (HP-01-006).

The receive-tree factory places the sender guard after intake, but a handler
can write or send *before* its tree runs (a P/X/A refusal, an expiry commit,
closing a pending ask) or have no tree at all.
:func:`sender_refusal` runs the same guard node from
:mod:`vultron.core.behaviors.sender_entitlement` as a one-node tree, so the
predicate stays in that module (HP-01-007) and the handler only asks.
"""

import py_trees

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases.received._bt_verdict import verdict_from_bt


def sender_refusal(
    dl: CasePersistence,
    receiving_actor_id: str,
    guard: py_trees.behaviour.Behaviour,
    *,
    label: str,
    sync_port: SyncActivityPort | None,
) -> HandlerResult | None:
    """Return ``REFUSED`` when *guard* turns the sender away, else ``None``.

    Nothing is written: the guard is a condition node, and the one-node tree
    carries no intake, so the activity is not archived here (the inbox has
    already stored what arrived).

    Args:
        dl: The receiving store.
        receiving_actor_id: The actor whose replica the activity is applied to.
        guard: A sender-entitlement condition node.
        label: Names the handler's step in the refusal reason.
        sync_port: The handler's sync port, passed on as every received
            bridge is (SYNC-02-003); the guard commits nothing.

    Raises:
        VultronBTInternalError: The guard failed on an internal error.
    """
    tree = py_trees.composites.Sequence(
        name=f"{label}SenderGuard", memory=False, children=[guard]
    )
    result = BTBridge(datalayer=dl, sync_port=sync_port).execute_with_setup(
        tree=tree, actor_id=receiving_actor_id
    )
    verdict = verdict_from_bt(tree, result, label=label)
    if verdict.disposition is HandlerDisposition.APPLIED:
        return None
    return verdict
