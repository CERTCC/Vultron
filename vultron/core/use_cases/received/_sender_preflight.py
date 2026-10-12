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

:func:`post_close_refusal_before_tree` does the same for the post-close write
boundary (CM-23-013): it runs the factory's own
:class:`~vultron.core.behaviors.case.nodes.post_close.CaseOpenToExternalWritesNode`
as a one-node tree, so a handler that writes or sends before its tree runs
asks the one guard rather than carrying a closed-case check of its own.
"""

import py_trees

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
)
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases._helpers import unaddressed_copy_refusal
from vultron.core.use_cases.received._bt_verdict import (
    post_close_refusal,
    verdict_from_bt,
)


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


def post_close_refusal_before_tree(
    dl: CasePersistence,
    receiving_actor_id: str,
    request: VultronEvent,
    *,
    case_id: str | None,
    sync_port: SyncActivityPort | None,
) -> HandlerResult | None:
    """Return ``REFUSED`` when the case is fully closed here, else ``None``.

    For a handler that writes or sends before its received tree runs: the
    factory's post-close guard (CM-23-013) would refuse the tree, but too
    late to stop what ran first.  Nothing is written or sent; the dropped
    activity is logged by the guard, with no reply (CM-23-017).

    Raises:
        VultronBTInternalError: The guard failed on an internal error.
    """
    tree = py_trees.composites.Sequence(
        name="PostClosePreflight",
        memory=False,
        children=[CaseOpenToExternalWritesNode(case_id=case_id)],
    )
    result = BTBridge(datalayer=dl, sync_port=sync_port).execute_with_setup(
        tree=tree, actor_id=receiving_actor_id, activity=request
    )
    if (refusal := post_close_refusal(tree)) is not None:
        return refusal
    verdict_from_bt(tree, result, label="PostClosePreflight")
    return None


def door_refusal(
    dl: CasePersistence,
    receiving_actor_id: str,
    request: VultronEvent,
    guard: py_trees.behaviour.Behaviour,
    *,
    case_id: str,
    label: str,
    sync_port: SyncActivityPort | None,
) -> HandlerResult | None:
    """The first refusal owed before a handler writes, or ``None``.

    In order: the case is fully closed (CM-23-013), the copy was not
    addressed to this receiver (HP-01-005), the sender is not entitled
    (HP-01-006).  None of the three writes or sends anything.
    """
    return (
        post_close_refusal_before_tree(
            dl,
            receiving_actor_id,
            request,
            case_id=case_id,
            sync_port=sync_port,
        )
        or unaddressed_copy_refusal(receiving_actor_id, request, label=label)
        or sender_refusal(
            dl, receiving_actor_id, guard, label=label, sync_port=sync_port
        )
    )
