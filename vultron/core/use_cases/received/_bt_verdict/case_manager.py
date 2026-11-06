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

"""Verdicts owed when the CASE_MANAGER gate turned this actor away.

A CASE_MANAGER-addressed message that reaches an actor without that role
was misaddressed, so it is ``REFUSED`` (HP-01-005); so is an act naming a
case this store does not hold or one whose roster names no CASE_MANAGER.
"""

import logging

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.conditions import (
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.case.nodes.reference_list import (
    CaseReferenceEditPendingNode,
)
from vultron.core.behaviors.sync.ledger_position_stage import (
    LEDGER_POSITION_GATE_NAME,
)
from vultron.core.behaviors.sync.sender_sequence_stage import (
    SENDER_SEQUENCE_GATE_NAME,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases.received._bt_verdict.tree_lookup import (
    _HasRoot,
    _root,
    find_node,
)

logger = logging.getLogger(__name__)

#: The gates of the stages every case tree runs ahead of the act.
_STAGE_GATE_NAMES = frozenset(
    {LEDGER_POSITION_GATE_NAME, SENDER_SEQUENCE_GATE_NAME}
)


def not_case_manager(tree: py_trees.behaviour.Behaviour | _HasRoot) -> bool:
    """True when the tree's CASE_MANAGER gate found this actor is not it.

    ``create_case_manager_gated_tree`` inverts ``CheckIsCaseManagerNode`` so a
    non-manager skips the gated work and the tree still succeeds. The handler
    then has to say what that success was: see
    :func:`not_case_manager_refusal`.

    The gates around the factory's answer to a stamped ledger position and
    its judgment of the sender's number are not counted: they run ahead of
    the act's own guards in every case tree and answer the position or the
    number, not the act, so their skip at a replica says nothing about whom
    the act was addressed to (SYNC-18-007, SYNC-21-008).
    """
    root = _root(tree)
    position_answer = {
        id(node)
        for gate in root.iterate()
        if gate.name in _STAGE_GATE_NAMES
        for node in gate.iterate()
    }
    return any(
        isinstance(node, CheckIsCaseManagerNode)
        and node.status == Status.FAILURE
        and id(node) not in position_answer
        for node in root.iterate()
    )


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


def case_manager_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    verdict: HandlerResult,
    dl: CasePersistence,
    case_id: str,
) -> HandlerResult:
    """*verdict*, or the refusal owed when the gate turned this actor away.

    For a handler whose tree does nothing at an actor that is not the
    CASE_MANAGER: its run succeeds there with every gated step skipped, and
    that success is a misaddressed message, neither an applied one nor a
    repeat (HP-01-005).  A redelivery to such an actor is refused the same
    way: it was never this actor's to act on.  A ``SKIPPED`` from a repeat
    guard that ends the run before the gate keeps its ``SKIPPED``, because
    the gate never ran.  A ``REFUSED`` verdict is returned as it is.
    """
    if verdict.disposition is HandlerDisposition.REFUSED:
        return verdict
    refusal = not_case_manager_refusal(tree, dl, case_id)
    return verdict if refusal is None else refusal


def unheld_case_refusal(
    dl: CasePersistence, case_id: str, activity_id: str, label: str
) -> HandlerResult | None:
    """The refusal owed to an act that names a case this store does not hold.

    ``Join``, ``Ignore`` and ``Leave`` of a case and the ownership-transfer
    ``Offer`` name their case and carry no copy of it (ADR-0165): the
    receiver reads every detail from the case it holds, so a case it does not
    hold leaves it nothing to act on, and the act is ``REFUSED`` naming the
    activity and the case.  ``None`` when the store holds the case.
    """
    if dl.read_case(case_id) is not None:
        return None
    logger.warning(
        "%s '%s' names case '%s', which this actor does not hold — REFUSED",
        label,
        activity_id,
        case_id,
    )
    return HandlerResult.refused(
        f"{label} '{activity_id}' names unknown case '{case_id}'"
    )


def case_manager_absence_refusal(
    dl: CasePersistence, case_id: str
) -> HandlerResult | None:
    """The refusal owed when this store has no CASE_MANAGER to defer to.

    ``REFUSED`` for a case this store does not hold and for a case whose
    roster names no CASE_MANAGER (CM-02-014); ``None`` when the case names
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
    return case_manager_verdict(tree, verdict, dl, case_id)
