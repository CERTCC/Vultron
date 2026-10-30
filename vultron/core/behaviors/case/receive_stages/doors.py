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

"""The door guards of a received tree (CLP-10-010, HP-01-005, CM-23-013).

Intake is followed by the post-close guard, the addressee check, the
closed-sender check, any case resolution and the sender guard.  Split out of
``receive_activity_tree.py`` (CS-18-001).
"""

import py_trees

from vultron.core.behaviors.case.nodes.addressee import (
    ADDRESSEE_EXEMPTIONS,
    ActivityAddressedToReceiverNode,
    AddresseeExemption,
)
from vultron.core.behaviors.case.nodes.case_lookup import CaseResolving
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
    PostCloseExemption,
)
from vultron.core.behaviors.case.receive_stages.guards import refusal_stage
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.exemption_registry import require_registered
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    ClosedSenderCheck,
    LedgerActivityContext,
    SenderContext,
    closed_sender_door,
    compose_sender_guard,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.errors import VultronWiringError


def addressee_stage(
    name: str, exemption: AddresseeExemption | None
) -> list[py_trees.behaviour.Behaviour]:
    """The addressee door guard, labelled with the tree's name (HP-01-005).

    Nothing for a tree that passes a registered exemption.

    Raises:
        VultronWiringError: *exemption* is not registered in
            ``ADDRESSEE_EXEMPTIONS``.
    """
    if exemption is None:
        return [ActivityAddressedToReceiverNode(label=name)]
    require_registered(
        exemption,
        ADDRESSEE_EXEMPTIONS,
        where=f"create_receive_activity_tree({name})",
        kind="addressee",
        registry_name="ADDRESSEE_EXEMPTIONS",
        spec_id="HP-01-005",
    )
    return []


def post_close_stage(
    name: str,
    intake: IntakeReceivedActivityNode,
    guard_case_id: str | None,
    exemption: PostCloseExemption | None,
    reply: list[py_trees.behaviour.Behaviour],
) -> list[py_trees.behaviour.Behaviour]:
    """The post-close write-boundary guard, with its optional reply.

    Returns the nodes to place directly after intake: nothing for an exempt
    tree, the bare :class:`CaseOpenToExternalWritesNode` when the tree owes
    no reply, or a refusal stage that runs *reply* only when the guard
    refuses (CM-23-013).

    Raises:
        VultronWiringError: an exempt tree passes a reply (the reply could
            never run), or a reply node is not emit-capable or writes state.
    """
    if exemption is not None:
        if reply:
            raise VultronWiringError(
                f"create_receive_activity_tree({name}): post_close_reply"
                f" needs the post-close guard, but the tree is exempt"
                f" ({exemption}) (CM-23-013)"
            )
        return []
    guard = CaseOpenToExternalWritesNode(
        case_id=guard_case_id, name="CaseOpenToExternalWrites"
    )
    if not reply:
        return [guard]
    return [
        refusal_stage(
            name,
            intake,
            [guard],
            reply,
            guard_case_id,
            stage_name="PostCloseStage",
            guards_name="PostCloseGuard",
            gate_suffix="PostCloseReplyIfCaseManager",
            argument="post_close_reply",
        )
    ]


def closed_sender_stage(
    name: str, case_id: str | None, check: ClosedSenderCheck
) -> py_trees.behaviour.Behaviour:
    """The closed-sender door guard on the tree's case (CM-23-018).

    Raises:
        VultronWiringError: The tree names no case to check the sender's
            closure on.
    """
    if case_id is None:
        raise VultronWiringError(
            f"create_receive_activity_tree({name}): closed_sender needs the"
            " tree's case_id or manager_case_id (CM-23-018)"
        )
    return closed_sender_door(case_id, check)


def case_resolution_stage(
    name: str,
    steps: list[py_trees.behaviour.Behaviour],
    *,
    sender_guarded: bool,
) -> list[py_trees.behaviour.Behaviour]:
    """The steps that resolve the case the sender guard reads (HP-01-025).

    They run between the post-close guard and the sender guard, so they may
    only read: a sender with no standing must leave nothing behind
    (HP-01-006).  A step may publish what it resolved on the blackboard
    (``/case_id``), which is not a DataLayer write.  Not every writer carries
    a marker (a ledger commit, replication state), so a step is admitted by
    the :class:`~vultron.core.behaviors.case.nodes.case_lookup.CaseResolving`
    marker on each of its leaves, and refused if any node in it is also
    marked as a state writer or an emitter.

    Raises:
        VultronWiringError: steps are given without a sender guard to run
            them for, or a step holds a leaf without the ``CaseResolving``
            marker, a state writer or an emit-capable node.
    """
    if not steps:
        return []
    where = f"create_receive_activity_tree({name})"
    if not sender_guarded:
        raise VultronWiringError(
            f"{where}: case_resolution resolves the case the sender guard"
            " reads; pass it only with a sender_rule (HP-01-025)"
        )
    nodes = [n for root in steps for n in root.iterate()]
    refused = sorted(
        {
            type(n).__name__
            for n in nodes
            if isinstance(n, (StateWriteCapable, EmitCapable))
            or (not n.children and not isinstance(n, CaseResolving))
        }
    )
    if refused:
        raise VultronWiringError(
            f"{where}: case_resolution runs before the sender guard, so it"
            " may only read; each leaf must be a CaseResolving node that"
            f" writes no state and emits nothing; found {refused}"
            " (HP-01-006)"
        )
    return steps


def sender_guard_stage(
    name: str,
    case_id: str | None,
    manager_case_id: str | None,
    sender_rule: SenderRule | None,
    sender_context: SenderContext | None,
) -> py_trees.behaviour.Behaviour | None:
    """The tree's sender guard, composed from the declared rule (HP-01-025).

    A tree that commits (``case_id`` set) must judge the sender against that
    case, and a tree that commits nothing but writes for a CASE_MANAGER
    (*manager_case_id*, the close-case tree) against that one; a tree with
    neither judges it against the case its *sender_context* names.  A
    :class:`~vultron.core.behaviors.sender_guard.LedgerActivityContext`
    reads the case from the activity at run time, so it is given only to a
    tree with no commit case at build time.
    """
    if sender_rule is None:
        if sender_context is not None:
            raise VultronWiringError(
                f"{name}: sender_context is given without a sender_rule"
            )
        return None
    if sender_context is None:
        raise VultronWiringError(
            f"{name}: sender_rule needs a sender_context (HP-01-025)"
        )
    if isinstance(sender_context, LedgerActivityContext):
        context_case, tree_case = None, case_id
    else:
        context_case = sender_context.case_id
        tree_case = case_id or manager_case_id
    if tree_case is not None and context_case != tree_case:
        raise VultronWiringError(
            f"{name}: sender_context names case {context_case!r}"
            f" but the tree's case is {tree_case!r} (HP-01-025)"
        )
    return compose_sender_guard(sender_rule, sender_context)
