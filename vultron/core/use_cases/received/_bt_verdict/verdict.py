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

"""The default readings of a finished received-side BT run (ADR-0095).

:func:`verdict_from_bt` for a tree that judges, :func:`intake_verdict` for
a tree whose state change is intake, and :func:`applied_or_raise` for a tree
that only stores or commits.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTExecutionResult
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.helpers import WIRING_UNAVAILABLE_MESSAGES
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.use_cases.received._bt_verdict.door import (
    door_refusal,
    incomplete_activity_refusal,
)
from vultron.core.use_cases.received._bt_verdict.tree_lookup import (
    _HasRoot,
    failure_reason,
    find_node,
)
from vultron.errors import VultronBTInternalError


def verdict_from_bt(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    result: BTExecutionResult,
    *,
    label: str,
) -> HandlerResult:
    """The default ``HandlerResult`` for a finished received-side BT run.

    The door guards' refusals (:func:`door_refusal`) and an incomplete
    activity's refusal (:func:`incomplete_activity_refusal`) are read first
    and keep their guard's own reason; any other refusal is prefixed with
    *label*.

    Args:
        tree: The tree that ran (or its ``BehaviourTree`` wrapper).
        result: What ``BTBridge`` returned for it.
        label: Names the handler's step in a reason, e.g. ``"EngageCaseBT"``.

    Raises:
        VultronBTInternalError: The run failed on an internal error.
    """
    if result.status == Status.SUCCESS:
        return HandlerResult.applied()
    if result.leader_skipped:
        return HandlerResult.skipped("not the replication leader")
    if (refusal := door_refusal(tree)) is not None:
        return refusal
    if (refusal := incomplete_activity_refusal(tree)) is not None:
        # The guard's message is the whole reason, with no label (CLP-10-018).
        return refusal
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
        # raising. It only covers the messages exported from
        # helpers/messages.py; a node with a custom wiring-failure message
        # would slip past it.
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
    of a redelivery, ``SKIPPED`` (HP-01-014).  A tree may also carry effect
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
    a verdict on the sender — except the door guards every received tree
    carries, whose refusal is returned (:func:`door_refusal`).

    Raises:
        VultronBTInternalError: The run failed for any reason.
    """
    if (refusal := door_refusal(tree)) is not None:
        # The refusals such a tree can meet: the case closed (CM-23-013), or
        # the copy was not addressed to this receiver (HP-01-005).
        return refusal
    verdict = verdict_from_bt(tree, result, label=label)
    if verdict.disposition is HandlerDisposition.REFUSED:
        raise VultronBTInternalError(verdict.reason or label)
    return verdict
