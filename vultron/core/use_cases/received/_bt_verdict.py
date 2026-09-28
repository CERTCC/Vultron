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

"""Turn a received-side BT run into the handler's ``HandlerResult`` (#2255).

A tree's root status says only whether it succeeded. A handler has to report
more than that (HP-01-003, ADR-0095): a benign no-op is ``SKIPPED``, a rejected
assertion is ``REFUSED``, and a programming error is neither — it propagates.

:func:`verdict_from_bt` applies the default reading of a finished run:

- ``SUCCESS`` → ``APPLIED``.
- A leadership skip (the tree never ran) → ``SKIPPED``.
- ``internal_error``, or a node missing its DataLayer or a port → raise
  :class:`~vultron.errors.VultronBTInternalError`.
- Any other ``FAILURE`` → ``REFUSED``, with the failing leaf's reason.

:func:`applied_or_raise` is the variant for a tree that only stores or commits:
there any ``FAILURE`` raises.

Handlers refine it where the tree says more: a guard whose ``FAILURE`` is a
duplicate, a role gate that reports "not my job" as ``SUCCESS``. They ask with
:func:`node_failed` / :func:`node_succeeded`, which look a node up by type the
way ``_filter_node_wholly_refused`` in ``status.py`` does, because a node's
``feedback_message`` usually embeds ids and is not a stable key.
"""

from typing import Protocol, TypeVar

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.helpers import WIRING_UNAVAILABLE_MESSAGES
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.errors import VultronBTInternalError

_N = TypeVar("_N", bound=py_trees.behaviour.Behaviour)


class _HasRoot(Protocol):
    root: py_trees.behaviour.Behaviour


def _root(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
) -> py_trees.behaviour.Behaviour:
    if isinstance(tree, py_trees.behaviour.Behaviour):
        return tree
    return tree.root


def find_node(
    tree: py_trees.behaviour.Behaviour | _HasRoot, node_type: type[_N]
) -> _N | None:
    """Return the first node of *node_type* in *tree*, or ``None``."""
    for node in _root(tree).iterate():
        if isinstance(node, node_type):
            return node
    return None


def find_named(
    tree: py_trees.behaviour.Behaviour | _HasRoot, name: str
) -> py_trees.behaviour.Behaviour | None:
    """Return the first node called *name* in *tree*, or ``None``.

    For composites, which share a class and differ only by name.
    """
    for node in _root(tree).iterate():
        if node.name == name:
            return node
    return None


def _any_with_status(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    node_type: type[py_trees.behaviour.Behaviour],
    status: Status,
) -> bool:
    return any(
        isinstance(node, node_type) and node.status == status
        for node in _root(tree).iterate()
    )


def node_failed(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    node_type: type[py_trees.behaviour.Behaviour],
) -> bool:
    """True when any node of *node_type* ran and returned ``FAILURE``.

    Any, not first: one node type often sits on several branches (the Reject
    emitter on both the missing-case and hash-mismatch arms of a sync tree).
    """
    return _any_with_status(tree, node_type, Status.FAILURE)


def node_succeeded(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    node_type: type[py_trees.behaviour.Behaviour],
) -> bool:
    """True when any node of *node_type* ran and returned ``SUCCESS``."""
    return _any_with_status(tree, node_type, Status.SUCCESS)


def not_case_manager(tree: py_trees.behaviour.Behaviour | _HasRoot) -> bool:
    """True when the tree's CASE_MANAGER gate found this actor is not it.

    ``create_case_manager_gated_tree`` inverts ``CheckIsCaseManagerNode`` so a
    non-manager skips the gated work and the tree still succeeds. When that
    gated work is all the handler does, the success is a correct no-op.
    """
    from vultron.core.behaviors.case.nodes.conditions import (
        CheckIsCaseManagerNode,
    )

    return node_failed(tree, CheckIsCaseManagerNode)


def failure_reason(
    tree: py_trees.behaviour.Behaviour | _HasRoot, result: BTExecutionResult
) -> str:
    """The reason a run failed, never empty.

    The failing leaf's message comes first (BT-13-001). A node that *raised*
    never set a status, so its reason is only on ``result.feedback_message``.
    """
    return (
        BTBridge.get_failure_reason(_root(tree))
        or result.feedback_message
        or "behavior tree failed without a reason"
    )


def verdict_from_bt(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    result: BTExecutionResult,
    *,
    label: str,
) -> HandlerResult:
    """The default ``HandlerResult`` for a finished received-side BT run.

    Args:
        tree: The tree that ran (or its ``BehaviourTree`` wrapper).
        result: What ``BTBridge`` returned for it.
        label: Names the handler's step in a reason, e.g. ``"UpdateCaseBT"``.

    Raises:
        VultronBTInternalError: The run failed on an internal error.
    """
    if result.status == Status.SUCCESS:
        return HandlerResult.applied()
    if result.leader_skipped:
        return HandlerResult.skipped("not the replication leader")
    if result.internal_error:
        raise VultronBTInternalError(f"{label}: {result.feedback_message}")
    reason = failure_reason(tree, result)
    if reason in WIRING_UNAVAILABLE_MESSAGES:
        # The node was composed without a dependency: our fault, not the
        # sender's, so it must not read as a refusal (ADR-0095).
        raise VultronBTInternalError(f"{label}: {reason}")
    return HandlerResult.refused(f"{label}: {reason}")


def applied_or_raise(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    result: BTExecutionResult,
    *,
    label: str,
) -> HandlerResult:
    """Like :func:`verdict_from_bt`, for a tree that judges nothing.

    A tree that only stores or commits what the handler has already accepted
    fails only when the DataLayer does, so its failure is a local fault, never
    a verdict on the sender.

    Raises:
        VultronBTInternalError: The run failed for any reason.
    """
    verdict = verdict_from_bt(tree, result, label=label)
    if verdict.disposition is HandlerDisposition.REFUSED:
        raise VultronBTInternalError(verdict.reason or label)
    return verdict


__all__ = [
    "applied_or_raise",
    "failure_reason",
    "find_named",
    "find_node",
    "node_failed",
    "node_succeeded",
    "not_case_manager",
    "verdict_from_bt",
]
