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
can write or send *before* its tree runs (a P/X/A refusal, closing a pending
ask) or have no tree at all.  An expiry is not such a write: it is a clock
decision inside the tree, after the sender guard (CLP-10-025).
:func:`rule_refusal` runs the guard the factory composes from the use case's
declared rule (HP-01-008) as a one-node tree, so the pre-flight and the tree
ask the same thing, the predicate stays in
:mod:`vultron.core.behaviors.sender_entitlement` (HP-01-007), and the handler
only asks.  A handler never builds a sender guard of its own; the ratchet in
``test/architecture/test_sender_entitlement_ratchet.py`` holds it to that.

:func:`post_close_refusal_before_tree` does the same for the post-close write
boundary (CM-23-013): it runs the factory's own
:class:`~vultron.core.behaviors.case.nodes.post_close.CaseOpenToExternalWritesNode`
as a one-node tree, so a handler that writes or sends before its tree runs
asks the one guard rather than carrying a closed-case check of its own.

:func:`repeat_answer_skip` does the same for the repeat guard of an answer to
an embargo Invite (CM-13-005): the Accept handler's P/X/A path writes or
sends before its tree runs, so a repeat must be caught first.
"""

import py_trees

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
)
from vultron.core.behaviors.embargo.nodes.answer_repeat import (
    EmbargoAnswerNotRecordedNode,
    case_manager_admits_embargo_answer_guard,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    SenderCheckContext,
    compose_sender_guard,
)
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases._helpers import unaddressed_copy_refusal
from vultron.core.use_cases.received._bt_verdict import (
    embargo_answer_repeat_verdict,
    find_node,
    post_close_refusal,
    verdict_from_bt,
)


def _guard_refusal(
    dl: CasePersistence,
    receiving_actor_id: str,
    guard: py_trees.behaviour.Behaviour,
    *,
    label: str,
    sync_port: SyncActivityPort | None,
    activity: VultronEvent | None = None,
) -> HandlerResult | None:
    """Return ``REFUSED`` when *guard* turns the sender away, else ``None``.

    Nothing is written: the guard is a condition node, and the one-node tree
    carries no intake, so the activity is not archived here (the inbox has
    already stored what arrived).

    Args:
        dl: The receiving store.
        receiving_actor_id: The actor whose replica the activity is applied to.
        guard: The sender guard composed from a declared rule.
        label: Names the handler's step in the refusal reason.
        sync_port: The handler's sync port, passed on as every received
            bridge is (SYNC-02-003); the guard commits nothing.
        activity: The received activity, placed on the blackboard for a guard
            that reads it.

    Raises:
        VultronBTInternalError: The guard failed on an internal error.
    """
    tree = py_trees.composites.Sequence(
        name=f"{label}SenderGuard", memory=False, children=[guard]
    )
    result = BTBridge(datalayer=dl, sync_port=sync_port).execute_with_setup(
        tree=tree, actor_id=receiving_actor_id, activity=activity
    )
    verdict = verdict_from_bt(tree, result, label=label)
    if verdict.disposition is HandlerDisposition.APPLIED:
        return None
    return verdict


def rule_refusal(
    dl: CasePersistence,
    receiving_actor_id: str,
    rule: SenderRule,
    context: SenderCheckContext,
    request: VultronEvent,
    *,
    label: str,
    sync_port: SyncActivityPort | None,
) -> HandlerResult | None:
    """Return ``REFUSED`` when the sender lacks the standing *rule* requires.

    The guard is the one the receive-tree factory composes from the use
    case's declared rule (HP-01-008), run ahead of a write the handler makes
    before its tree (a P/X/A refusal) or for a handler with no tree guard.

    Args:
        dl: The receiving store.
        receiving_actor_id: The actor whose replica the activity is applied to.
        rule: The use case's declared sender rule.
        context: The sender and the records the rule's kinds read.
        request: The received activity.
        label: Names the handler's step in the refusal reason.
        sync_port: The handler's sync port (SYNC-02-003).

    Raises:
        VultronBTInternalError: The guard failed on an internal error.
    """
    guard = compose_sender_guard(rule, context)
    if guard is None:
        return None  # the receiver's side admits any actor
    return _guard_refusal(
        dl,
        receiving_actor_id,
        guard,
        label=label,
        sync_port=sync_port,
        activity=request,
    )


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


def repeat_answer_skip(
    dl: CasePersistence,
    receiving_actor_id: str,
    *,
    case_id: str,
    embargo_id: str,
    answering_actor_id: str,
    answer: EmbargoConsentState,
    sync_port: SyncActivityPort | None,
) -> HandlerResult | None:
    """``SKIPPED`` when the answer repeats one already recorded, else ``None``.

    Runs the received answer tree's own repeat guard
    (:func:`~vultron.core.behaviors.embargo.nodes.answer_repeat.case_manager_admits_embargo_answer_guard`)
    as a one-node tree, for a handler that writes or sends before that tree
    runs.  A repeat of an answer the CASE_MANAGER already recorded, under any
    activity id, changes nothing, commits nothing and sends nothing
    (CM-13-005, HP-01-003).  A different answer is a consent change and
    passes, and so does every answer at a store that is not the case's
    CASE_MANAGER, whose tree then refuses it (HP-01-005).

    Raises:
        VultronBTInternalError: The guard failed on an internal error.
    """
    tree = case_manager_admits_embargo_answer_guard(
        case_id=case_id,
        embargo_id=embargo_id,
        answering_actor_id=answering_actor_id,
        answer=answer,
    )
    result = BTBridge(datalayer=dl, sync_port=sync_port).execute_with_setup(
        tree=tree, actor_id=receiving_actor_id
    )
    # Raises on an internal error; any other outcome but a repeat — a store
    # that is not the replication leader, say — is the handler's to report.
    verdict = verdict_from_bt(tree, result, label="EmbargoAnswerRepeatGuard")
    guard = find_node(tree, EmbargoAnswerNotRecordedNode)
    if guard is None or not guard.is_repeat:
        return None
    return embargo_answer_repeat_verdict(tree, verdict)


def door_refusal(
    dl: CasePersistence,
    receiving_actor_id: str,
    request: VultronEvent,
    rule: SenderRule,
    context: SenderCheckContext,
    *,
    label: str,
    sync_port: SyncActivityPort | None,
) -> HandlerResult | None:
    """The first refusal owed before a handler writes, or ``None``.

    In order: the case the *context* names is fully closed (CM-23-013), the
    copy was not addressed to this receiver (HP-01-005), the sender lacks the
    standing *rule* requires (HP-01-006, HP-01-008).  None of the three
    writes or sends anything.
    """
    return (
        post_close_refusal_before_tree(
            dl,
            receiving_actor_id,
            request,
            case_id=context.case_id,
            sync_port=sync_port,
        )
        or unaddressed_copy_refusal(receiving_actor_id, request, label=label)
        or rule_refusal(
            dl,
            receiving_actor_id,
            rule,
            context,
            request,
            label=label,
            sync_port=sync_port,
        )
    )
