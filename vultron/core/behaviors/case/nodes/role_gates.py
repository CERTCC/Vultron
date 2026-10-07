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
#  Carnegie Mellon®, CERTⓇ and CERT Coordination CenterⓇ are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Role-gated BT *composites*.

Sibling of :mod:`vfd_role_guards`, which holds role-gate *condition nodes*. This
module holds the composites that wrap other work in such a gate — the difference
being that a condition node answers a question, while these decide whether a
subtree runs at all.

Two gates: :func:`create_case_manager_gated_tree`, the single sanctioned shape
for "only the CASE_MANAGER may do this" (BTND-07-005) — canonical ledger commits
and the note-attachment path both build on it — and its complement
:func:`create_participant_replica_gated_tree`, for the work a received tree does
only when the executing actor is *not* the CASE_MANAGER (RSH-08-003).
"""

import py_trees

from vultron.core.behaviors.case.nodes.conditions import (
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.sender_entitlement import SenderIsCaseManagerNode

__all__ = [
    "create_case_manager_gated_tree",
    "create_role_scoped_sender_guard",
    "create_participant_replica_gated_tree",
]


def create_role_scoped_sender_guard(
    name: str,
    case_id: str,
    at_case_manager: py_trees.behaviour.Behaviour,
) -> py_trees.composites.Selector:
    """A sender guard whose rule depends on the receiver's role (ADR-0115).

    At the CASE_MANAGER the sender must satisfy *at_case_manager*; at any other
    participant replica the only entitled sender is the CASE_MANAGER itself,
    because replicas learn of a change from the manager's ledger fan-out
    (SYNC-02-002), never from a peer's message.

    Structure::

        <name> (Selector)
        ├── AtCaseManager (Sequence): CheckIsCaseManager, <at_case_manager>
        └── AtReplica (Sequence): Inverter(CheckIsCaseManager), SenderIsCaseManager

    The Selector fails when the receiver is the manager and *at_case_manager*
    fails: the replica arm's inverted role check fails too.
    """
    return py_trees.composites.Selector(
        name=name,
        memory=False,
        children=[
            py_trees.composites.Sequence(
                name="AtCaseManager",
                memory=False,
                children=[
                    CheckIsCaseManagerNode(case_id=case_id),
                    at_case_manager,
                ],
            ),
            py_trees.composites.Sequence(
                name="AtReplica",
                memory=False,
                children=[
                    py_trees.decorators.Inverter(
                        name="InvertIsNotCaseManager",
                        child=CheckIsCaseManagerNode(case_id=case_id),
                    ),
                    SenderIsCaseManagerNode(case_id=case_id),
                ],
            ),
        ],
    )


def _wrap_children(
    name: str,
    children: list[py_trees.behaviour.Behaviour],
    body_name: str | None,
) -> py_trees.behaviour.Behaviour:
    """One child runs bare; several become a Sequence so a mid-run FAILURE propagates."""
    if len(children) == 1:
        return children[0]
    return py_trees.composites.Sequence(
        name=body_name or f"{name}Body",
        memory=False,
        children=children,
    )


def create_case_manager_gated_tree(
    name: str,
    case_id: str | None,
    children: list[py_trees.behaviour.Behaviour],
    body_name: str | None = None,
    case_may_be_absent: bool = False,
) -> py_trees.composites.Selector:
    """Run *children* only when the executing actor holds ``CVDRole.CASE_MANAGER``.

    Reimplementing this boilerplate is forbidden (BTND-07-005) for a concrete
    reason, not a stylistic one: the obvious hand-rolled form,
    ``Selector[Sequence[check, *children], Success]``, masks a genuine failure of
    *children* as a benign skip, because the ``Success`` fallback cannot tell
    "not the case manager" from "am the case manager and the work failed".

    Structure::

        <name> (Selector)
        ├── SkipIfNotCaseManager (Sequence)
        │   └── Inverter(CheckIsCaseManagerNode)  # SUCCESS when NOT case manager
        └── <children>                            # only reached when IS case manager

    The ``Inverter`` is what separates the two FAILURE modes:

    - Actor is NOT the case manager → ``Inverter`` converts FAILURE→SUCCESS,
      ``SkipIfNotCaseManager`` succeeds, Selector returns SUCCESS (skip).
    - Actor IS the case manager but the work fails → ``Inverter`` converts
      SUCCESS→FAILURE, ``SkipIfNotCaseManager`` fails, Selector tries the
      children, which return FAILURE, and the Selector returns FAILURE
      (propagating the error rather than swallowing it).

    Note that the gate compares the *blackboard* ``actor_id`` against the case's
    CASE_MANAGER participant, so the executing actor, its store and the role
    holder must be one actor (BT-05-005, BT-05-006). Letting any two drift makes
    the gate skip silently.

    Args:
        name: Name for the root Selector.
        case_id: Case whose CASE_MANAGER role gates the children.
        children: Nodes to run when the gate passes. More than one is wrapped in
            a Sequence so a mid-sequence failure still propagates.
        body_name: Name for that wrapping Sequence. Defaults to ``{name}Body``.
        case_may_be_absent: Read a case the executing actor does not hold as
            "not the CASE_MANAGER" instead of an anomaly; see
            :class:`CheckIsCaseManagerNode`.

    Returns:
        The gated root Selector.
    """
    gated = _wrap_children(name, children, body_name)

    return py_trees.composites.Selector(
        name=name,
        memory=False,
        children=[
            py_trees.composites.Sequence(
                name="SkipIfNotCaseManager",
                memory=False,
                children=[
                    py_trees.decorators.Inverter(
                        name="InvertIsNotCaseManager",
                        child=CheckIsCaseManagerNode(
                            case_id=case_id,
                            case_may_be_absent=case_may_be_absent,
                        ),
                    ),
                ],
            ),
            gated,
        ],
    )


def create_participant_replica_gated_tree(
    name: str,
    case_id: str | None,
    children: list[py_trees.behaviour.Behaviour],
    body_name: str | None = None,
    case_may_be_absent: bool = False,
) -> py_trees.composites.Selector:
    """Run *children* only when the executing actor is **not** the CASE_MANAGER.

    The complement of :func:`create_case_manager_gated_tree`, for a received
    tree whose manager-side and replica-side effects differ (EP-09-001 versus
    EP-09-003): the manager adjudicates and relays, a participant replica
    records what arrived.  The two gates placed side by side in one Sequence
    are mutually exclusive, so exactly one arm runs.

    Structure::

        <name> (Selector)
        ├── CheckIsCaseManagerNode        # SUCCESS when IS case manager → skip
        └── <children>                    # only reached when NOT case manager

    No ``Inverter`` is needed here and no failure is masked: the first arm is a
    pure condition, so a Selector that falls through to *children* reports
    their FAILURE as its own.

    Args:
        name: Name for the root Selector.
        case_id: Case whose CASE_MANAGER role gates the children.
        children: Nodes to run when the executing actor is not the manager.
            More than one is wrapped in a Sequence so a mid-sequence failure
            still propagates.
        body_name: Name for that wrapping Sequence. Defaults to ``{name}Body``.
        case_may_be_absent: Read a case the executing actor does not hold as
            "not the CASE_MANAGER" instead of an anomaly; see
            :class:`CheckIsCaseManagerNode`.

    Returns:
        The gated root Selector.
    """
    gated = _wrap_children(name, children, body_name)

    return py_trees.composites.Selector(
        name=name,
        memory=False,
        children=[
            CheckIsCaseManagerNode(
                case_id=case_id,
                name="SkipIfCaseManager",
                case_may_be_absent=case_may_be_absent,
            ),
            gated,
        ],
    )
