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
more than that (HP-01-003, ADR-0095): a benign no-op is ``SKIPPED``, a refused
assertion is ``REFUSED``, and a programming error is neither — it propagates.

:func:`verdict_from_bt` applies the default reading of a finished run:

- ``SUCCESS`` → ``APPLIED``.
- A leadership skip (the tree never ran) → ``SKIPPED``.
- ``internal_error``, or a node missing its DataLayer or a port → raise
  :class:`~vultron.errors.VultronBTInternalError`.
- The post-close guard refused (CM-23-013) → ``REFUSED``, ahead of any other
  reading of the failure.
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
from vultron.core.behaviors.case.nodes.addressee import (
    ActivityAddressedToReceiverNode,
)
from vultron.core.behaviors.case.nodes.conditions import (
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.case.nodes.diversion_stage import DiversionStage
from vultron.core.behaviors.case.nodes.incomplete_activity import (
    ActivityIncompleteNode,
)
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.ownership_offer_guard import (
    NoOpenOwnershipOfferNode,
    OwnershipOfferOpenNode,
)
from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
)
from vultron.core.behaviors.case.nodes.reference_list import (
    CaseReferenceEditPendingNode,
)
from vultron.core.behaviors.case.nodes.role_offer_guard import (
    RoleOfferAdmissibleNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
)
from vultron.core.behaviors.embargo.nodes.answer_repeat import (
    EmbargoAnswerNotRecordedNode,
)
from vultron.core.behaviors.embargo.nodes.pxa_refusal import (
    EmbargoInviteNotYetRefusedNode,
)
from vultron.core.behaviors.embargo.nodes.withdrawal import (
    IsWithdrawableEmbargoNode,
)
from vultron.core.behaviors.helpers import WIRING_UNAVAILABLE_MESSAGES
from vultron.core.behaviors.report.nodes.conditions import (
    CheckParticipantRMState,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronBTInternalError, VultronWiringError

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


def named_node_status(
    tree: py_trees.behaviour.Behaviour | _HasRoot, name: str
) -> Status:
    """The last status of the node called *name* in *tree*.

    For nodes that share a class and differ only by their place in the tree,
    such as the role checks of the announce tree's two arms.

    Raises:
        VultronWiringError: *tree* has no node called *name*, so the caller's
            verdict would silently skip the branch it reads.
    """
    node = find_named(tree, name)
    if node is None:
        raise VultronWiringError(f"no node called {name!r} in the tree")
    return node.status


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


def door_guards_admitted(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
) -> bool:
    """True when the run got past every door guard of its tree (CLP-10-010).

    The intake, the post-close guard, the addressee check and the sender
    guard all ran and succeeded, so the delivery reached its clock decisions
    and precondition guards, whatever those then decided.  Asked of the
    factory's record of its door guards, so the answer does not depend on
    which guard the tree runs first.

    Raises:
        VultronWiringError: *tree* was not built by
            :func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`.
    """
    root = _root(tree)
    if not isinstance(root, ReceivedActivityTree):
        raise VultronWiringError(
            f"door_guards_admitted: '{root.name}' is not a received-activity"
            " tree, so it has no door guards to ask about (CLP-10-010)"
        )
    return root.door_guards_admitted


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
    if (refusal := case_manager_absence_refusal(dl, case_id)) is not None:
        return refusal
    return HandlerResult.refused(f"not the CASE_MANAGER of case '{case_id}'")


def case_manager_absence_refusal(
    dl: CasePersistence, case_id: str
) -> HandlerResult | None:
    """The refusal owed when this store has no CASE_MANAGER to defer to.

    ``REFUSED`` for a case this store does not hold and for a case whose
    roster names no CASE_MANAGER (CM-24-006); ``None`` when the case names
    one.  A handler whose CASE_MANAGER gate turned this actor away calls it
    to tell those two cases from a replica that simply is not the
    CASE_MANAGER, which :func:`not_case_manager_refusal` refuses and some
    handlers read otherwise.
    """
    case = dl.read(case_id)
    if not isinstance(case, VulnerabilityCase):
        return HandlerResult.refused(f"unknown case '{case_id}'")
    if resolve_case_manager_id(case, dl) is None:
        return HandlerResult.refused(f"case '{case_id}' has no CASE_MANAGER")
    return None


def reference_edit_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
    dl: CasePersistence,
    case_id: str,
) -> HandlerResult:
    """Refine the verdict of a tree that attaches or detaches a case reference.

    Such a tree carries a ``CaseReferenceEditPendingNode`` duplicate guard: its
    ``FAILURE`` with ``is_duplicate`` set is an idempotent re-delivery, so the
    handler reports ``SKIPPED`` rather than the default ``REFUSED``.  A tree that otherwise succeeded but
    whose CASE_MANAGER gate turned this actor away is a refusal (HP-01-005).
    """
    pending = find_node(tree, CaseReferenceEditPendingNode)
    if pending is not None and pending.is_duplicate:
        return HandlerResult.skipped(
            BTBridge.get_failure_reason(_root(tree))
            or "reference edit is already in effect"
        )
    if verdict.disposition is HandlerDisposition.APPLIED:
        refusal = not_case_manager_refusal(tree, dl, case_id)
        if refusal is not None:
            return refusal
    return verdict


def _redelivery_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    guard_type: (
        type[OwnershipOfferOpenNode]
        | type[NoOpenOwnershipOfferNode]
        | type[IsWithdrawableEmbargoNode]
    ),
    verdict: HandlerResult,
    fallback: str,
) -> HandlerResult:
    """``SKIPPED`` when *guard_type* failed the run as a redelivery."""
    guard = find_node(tree, guard_type)
    if guard is not None and guard.is_redelivery:
        return HandlerResult.skipped(guard.feedback_message or fallback)
    return verdict


def embargo_answer_repeat_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a repeated answer to an embargo Invite as ``SKIPPED``.

    :class:`~vultron.core.behaviors.embargo.nodes.answer_repeat.EmbargoAnswerNotRecordedNode`
    fails with ``is_repeat`` set when the sender's consent row already holds
    the answer, so nothing is committed or announced.  That is the benign
    no-op of a repeat, not a refusal (CM-13-005, HP-01-003).
    """
    guard = find_node(tree, EmbargoAnswerNotRecordedNode)
    if guard is not None and guard.is_repeat:
        return HandlerResult.skipped(
            guard.feedback_message or "embargo answer repeated"
        )
    return verdict


def embargo_withdrawal_redelivery_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a redelivered ``Leave(EmbargoEvent)`` as ``SKIPPED``.

    :class:`~vultron.core.behaviors.embargo.nodes.withdrawal.IsWithdrawableEmbargoNode`
    fails with ``is_redelivery`` set when the case's ledger already records
    the Leave, so nothing is re-applied.  That is the benign no-op of a
    redelivery, not a refusal (HP-01-003, MSM-07-010).
    """
    return _redelivery_verdict(
        tree,
        IsWithdrawableEmbargoNode,
        verdict,
        "Leave(EmbargoEvent) redelivered",
    )


def ownership_answer_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a redelivered reply to an ownership-transfer Offer as ``SKIPPED``.

    The reply's open-Offer guard — an
    :class:`~vultron.core.behaviors.case.nodes.ownership_offer_guard.OwnershipOfferOpenNode`,
    run right after the sender check, for the transferee's Accept or Reject
    or the offerer's withdrawal — fails with ``is_redelivery`` set when the
    reply is the one already ledgered as closing its Offer, so nothing is
    re-applied.  That is the benign no-op of a redelivery, not a refusal
    (HP-01-003, CM-21-011, CM-21-015).
    """
    return _redelivery_verdict(
        tree,
        OwnershipOfferOpenNode,
        verdict,
        "ownership-transfer reply redelivered",
    )


def ownership_offer_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a redelivered ownership-transfer Offer as ``SKIPPED``.

    :class:`~vultron.core.behaviors.case.nodes.ownership_offer_guard.NoOpenOwnershipOfferNode`
    fails with ``is_redelivery`` set when the CASE_MANAGER's ledger already
    records the Offer, so it is neither judged against a newer open Offer nor
    committed or forwarded again (HP-01-003, CM-21-014).
    """
    return _redelivery_verdict(
        tree,
        NoOpenOwnershipOfferNode,
        verdict,
        "ownership-transfer Offer redelivered",
    )


def role_offer_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
) -> HandlerResult:
    """Report a redelivered role Offer as ``SKIPPED``.

    :class:`~vultron.core.behaviors.case.nodes.role_offer_guard.RoleOfferAdmissibleNode`
    sets ``is_redelivery`` when the CASE_MANAGER's ledger already records the
    Offer (HP-01-003).  It fails when the forward is already stored, so
    nothing runs, and admits the run when it is not, so the run finishes the
    forward with the recorded entry reused (OX-06-002).  Either reads as
    ``SKIPPED``; when the guard admitted the run, a later refusal or failure
    keeps its own verdict.
    """
    guard = find_node(tree, RoleOfferAdmissibleNode)
    if guard is None or not guard.is_redelivery:
        return verdict
    if (
        guard.status is Status.FAILURE
        or verdict.disposition is HandlerDisposition.APPLIED
    ):
        return HandlerResult.skipped(
            guard.feedback_message or "role Offer redelivered"
        )
    return verdict


def rm_declaration_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
    label: str,
) -> HandlerResult:
    """Report a restated RM declaration as ``SKIPPED``, not ``APPLIED``.

    The idempotent exit of
    :func:`~vultron.core.behaviors.report.rm_declaration_tree.record_rm_declaration`
    (``CheckParticipantRMState``) succeeds when the sender's declared state is
    already recorded, so nothing changed locally: a correct no-op, not a
    refusal or a fault (RSH-08-002, ADR-0095).
    """
    if verdict.disposition is HandlerDisposition.APPLIED and node_succeeded(
        tree, CheckParticipantRMState
    ):
        return HandlerResult.skipped(
            f"{label}: the declared RM state is already recorded for the sender"
        )
    return verdict


def guard_refusal(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    node_type: type[py_trees.behaviour.Behaviour],
) -> HandlerResult | None:
    """``REFUSED`` with the guard's own reason when a *node_type* guard failed.

    ``None`` when no such guard ran and failed.  For a guard whose message
    is the whole refusal, so the reason carries no tree label:
    :class:`~vultron.core.behaviors.case.nodes.incomplete_activity.ActivityIncompleteNode`
    and the announce tree's trusted-sender guard.  A guard that never ran (a
    leadership skip, or the post-close guard refused first) is ``None``, so
    the handler falls through to :func:`verdict_from_bt`.  So does a guard
    that failed because it was composed without a dependency (a
    ``WIRING_UNAVAILABLE_MESSAGES`` reason): that is our fault, not the
    sender's, and :func:`verdict_from_bt` raises it (ADR-0095).
    """
    node = find_node(tree, node_type)
    if node is None or node.status != Status.FAILURE:
        return None
    if node.feedback_message in WIRING_UNAVAILABLE_MESSAGES:
        return None
    return HandlerResult.refused(
        node.feedback_message or f"{node.name} refused the activity"
    )


def addressee_refusal(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
) -> HandlerResult | None:
    """The refusal of a copy not addressed to this receiver (HP-01-005).

    ``None`` unless the tree's
    :class:`~vultron.core.behaviors.case.nodes.addressee.ActivityAddressedToReceiverNode`
    door guard refused; the reason is the guard's own, naming the receiver,
    the activity and its ``to``.
    """
    return guard_refusal(tree, ActivityAddressedToReceiverNode)


def taken_diversion(
    tree: py_trees.behaviour.Behaviour | _HasRoot, name: str
) -> DiversionStage | None:
    """The diversion stage *name* when it diverted the delivery, else ``None``.

    See :class:`~vultron.core.behaviors.case.nodes.diversion_stage.DiversionStage`
    (CLP-10-026): a taken diversion answered the delivery itself, so the
    tree's ``FAILURE`` is not a refusal of its own and the handler reads the
    stage instead.
    """
    for node in _root(tree).iterate():
        if (
            isinstance(node, DiversionStage)
            and node.name == name
            and node.taken
        ):
            return node
    return None


def pxa_refusal_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    name: str,
    answered: str,
) -> HandlerResult | None:
    """The verdict of a delivery the P/X/A refusal *name* diverted, else ``None``.

    ``SKIPPED`` when the ER *answered* names was already sent, so the
    redelivery is not refused twice (HP-01-003); otherwise ``REFUSED`` for
    the condition's reason (EMB-01-002, EMB-02-002), whether or not the ER
    could be sent.
    """
    stage = taken_diversion(tree, name)
    if stage is None:
        return None
    if node_failed(stage, EmbargoInviteNotYetRefusedNode):
        return HandlerResult.skipped(
            f"{answered} not refused again: the ER was already sent"
            " (HP-01-003)"
        )
    return HandlerResult.refused(
        stage.condition.feedback_message or f"{name}: P/X/A set"
    )


def incomplete_activity_refusal(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
) -> HandlerResult | None:
    """The refusal of an activity its handler's tree could not be built for.

    See :func:`guard_refusal` and
    :func:`~vultron.core.behaviors.case.intake_only_received_tree.create_incomplete_activity_received_tree`.
    """
    return guard_refusal(tree, ActivityIncompleteNode)


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


def post_close_refusal(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
) -> HandlerResult | None:
    """The refusal owed when the post-close guard dropped the activity.

    ``None`` unless the tree's
    :class:`~vultron.core.behaviors.case.nodes.post_close.CaseOpenToExternalWritesNode`
    refused: this actor is the case's CASE_MANAGER and the case is fully
    closed, so the tree recorded nothing (CM-23-013).  The verdict is
    ``REFUSED`` whatever the handler would otherwise read from the failure,
    so :func:`verdict_from_bt` and :func:`applied_or_raise` both ask this
    first, and a handler that maps a tree's failure itself asks it too.
    """
    for node in _root(tree).iterate():
        if (
            isinstance(node, CaseOpenToExternalWritesNode)
            and node.status == Status.FAILURE
        ):
            return HandlerResult.refused(
                node.feedback_message or "case is fully closed (CM-23-013)"
            )
    return None


def verdict_from_bt(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    result: BTExecutionResult,
    *,
    label: str,
) -> HandlerResult:
    """The default ``HandlerResult`` for a finished received-side BT run.

    The post-close refusal and an incomplete activity's refusal
    (:func:`incomplete_activity_refusal`) are read first and keep their
    guard's own reason; any other refusal is prefixed with *label*.

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
    if (refusal := post_close_refusal(tree)) is not None:
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
    a verdict on the sender — except the post-close guard every received tree
    carries, whose refusal is returned (CM-23-013).

    Raises:
        VultronBTInternalError: The run failed for any reason.
    """
    if (refusal := post_close_refusal(tree)) is not None:
        # The one refusal such a tree can meet: the case closed (CM-23-013).
        return refusal
    verdict = verdict_from_bt(tree, result, label=label)
    if verdict.disposition is HandlerDisposition.REFUSED:
        raise VultronBTInternalError(verdict.reason or label)
    return verdict


__all__ = [
    "addressee_refusal",
    "applied_or_raise",
    "case_manager_absence_refusal",
    "door_guards_admitted",
    "failure_reason",
    "find_named",
    "find_node",
    "guard_refusal",
    "incomplete_activity_refusal",
    "intake_verdict",
    "node_failed",
    "node_succeeded",
    "not_case_manager",
    "not_case_manager_refusal",
    "post_close_refusal",
    "pxa_refusal_verdict",
    "taken_diversion",
    "verdict_from_bt",
]
