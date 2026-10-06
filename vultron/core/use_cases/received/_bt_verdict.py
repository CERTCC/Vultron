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
duplicate, a role gate that skips as ``SUCCESS`` because this actor is not the
case's CASE_MANAGER. They ask with :func:`node_failed` /
:func:`node_succeeded`, which look a node up by type the way
``_filter_node_wholly_refused`` in ``status.py`` does, because a node's
``feedback_message`` usually embeds ids and is not a stable key.

A role-gate skip is not a benign no-op. The message was the CASE_MANAGER's to
act on and reached an actor that is not it, so the handler reports ``REFUSED``
(HP-01-005) through :func:`not_case_manager_refusal`; ``SKIPPED`` is reserved
for a duplicate or an otherwise idempotent re-delivery.
"""

from typing import Protocol, TypeVar

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.case.nodes.conditions import (
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.reference_list import (
    CaseReferenceEditPendingNode,
)
from vultron.core.behaviors.helpers import WIRING_UNAVAILABLE_MESSAGES
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence
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
    non-manager skips the gated work and the tree still succeeds. The handler
    then has to say what that success was: see
    :func:`not_case_manager_refusal`.
    """
    return node_failed(tree, CheckIsCaseManagerNode)


def not_case_manager_refusal(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    dl: CasePersistence,
    case_id: str,
) -> HandlerResult | None:
    """The refusal owed when the tree's CASE_MANAGER gate turned this actor away.

    ``None`` when the gate passed (or the tree has none), so a handler writes::

        if (refusal := not_case_manager_refusal(tree, dl, case_id)) is not None:
            return refusal

    The gate also fails for a case this store does not hold and for a case
    whose roster names no CASE_MANAGER at all, so the reason says which of the
    three it was. All are refusals (HP-01-005): a CASE_MANAGER-addressed
    message that reaches an actor without that role was misaddressed, and the
    receiver's inbox record says so rather than reporting a processed no-op.
    """
    if not not_case_manager(tree):
        return None
    case = dl.read(case_id)
    if not isinstance(case, VulnerabilityCase):
        return HandlerResult.refused(f"unknown case '{case_id}'")
    if resolve_case_manager_id(case, dl) is None:
        return HandlerResult.refused(f"case '{case_id}' has no CASE_MANAGER")
    return HandlerResult.refused(f"not the CASE_MANAGER of case '{case_id}'")


def reference_edit_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
    dl: CasePersistence,
    case_id: str,
) -> HandlerResult:
    """Refine the verdict of a tree that attaches or detaches a case reference.

    Such a tree carries a ``CaseReferenceEditPendingNode`` duplicate guard: its
    ``FAILURE`` is an idempotent re-delivery, so the handler reports ``SKIPPED``
    rather than the default ``REFUSED``.  A tree that otherwise succeeded but
    whose CASE_MANAGER gate turned this actor away is a refusal (HP-01-005).
    """
    if node_failed(tree, CaseReferenceEditPendingNode):
        return HandlerResult.skipped(
            BTBridge.get_failure_reason(_root(tree))
            or "reference edit is already in effect"
        )
    if verdict.disposition is HandlerDisposition.APPLIED:
        refusal = not_case_manager_refusal(tree, dl, case_id)
        if refusal is not None:
            return refusal
    return verdict


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
        # Coverage: nodes that raise VultronWiringError are caught by the
        # bridge and land in BTExecutionResult.internal_error (handled
        # above). This set-membership check catches the complementary path:
        # a node that sets feedback_message and returns FAILURE instead of
        # raising. It only covers the three messages exported from helpers.py;
        # a node with a custom wiring-failure message would slip past it.
        raise VultronBTInternalError(f"{label}: {reason}")
    return HandlerResult.refused(f"{label}: {reason}")


def intake_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    result: BTExecutionResult,
    *,
    label: str,
) -> HandlerResult:
    """The ``HandlerResult`` for a tree whose state change is intake.

    Intake archives what arrived, so a run that archived the activity is
    ``APPLIED`` and a run that found it already archived is the benign no-op
    of a redelivery, ``SKIPPED`` (HP-01-003).  A tree may also carry effect
    nodes, but only ones that are idempotent on a redelivery — a narrative
    log line, or a write that keeps an existing record (the invitee's trust
    anchor) — because they run again and the verdict still reads
    ``SKIPPED``.  The intake node reports which it was, so the handler does
    not inspect the DataLayer (ADR-0111).  A refused or failed run reads as
    :func:`verdict_from_bt` reads it.
    """
    verdict = verdict_from_bt(tree, result, label=label)
    if verdict.disposition is not HandlerDisposition.APPLIED:
        return verdict
    intake = find_node(tree, IntakeReceivedActivityNode)
    if intake is None:
        raise VultronBTInternalError(f"{label}: tree has no intake node")
    if intake.stored_anything:
        return verdict
    return HandlerResult.skipped(
        f"{label}: nothing arrived that was not already held"
    )


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
    "intake_verdict",
    "node_failed",
    "node_succeeded",
    "not_case_manager",
    "not_case_manager_refusal",
    "verdict_from_bt",
]
