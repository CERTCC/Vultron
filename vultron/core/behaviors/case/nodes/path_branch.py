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

"""The branch a received tree runs on some of its declared paths (ADR-0153).

A message type declares the paths it handles once, to the receive-tree
factory (HP-01-038), and the factory places the path door stage that resolves
the receiver's path (HP-01-035).  Part of a tree's work often belongs to one
of those paths rather than to all of them: the CASE_MANAGER's adjudication
guards are its alone, and an invitee's own record of an Invite is not the
CASE_MANAGER's to write (RSH-08-003).

A tree states that by passing an :class:`OnPaths` declaration in place of the
subtree, among its ``precondition_guards`` or its ``replica_effects``.  The
factory builds a :class:`PathBranch` at that spot, bound to the tree's path
stage::

    <name> (Selector)
    ├── SkipOff<name> (Sequence)
    │   └── Inverter(<on any of the branch's paths>)   # SUCCESS off them
    └── <children>                                     # only on them

The branch asks no role question of its own: it reads the answer the path
stage already recorded, through
:class:`~vultron.core.behaviors.case.nodes.received_path.CheckReceivedPathNode`,
so the role is read once per message (HP-01-036, HP-01-037).  That is what
makes the branch the replacement for the role-gate composites a received tree
used to build for itself: BT-17-001's intent still holds for the manager
path, now as the branch that names it.

The ``Inverter`` keeps the two FAILURE modes apart, for the same reason
:func:`~vultron.core.behaviors.case.nodes.role_gates.create_case_manager_gated_tree`
needs one: a bare ``Success`` fallback cannot tell "this receiver is on
another path" from "this receiver is on the branch's path and the work
failed", and would report the second as a benign skip.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.act_transaction import ActTransaction
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
    ReceivedPathNode,
    on_any_of_paths,
)
from vultron.errors import VultronWiringError

__all__ = [
    "OnPaths",
    "PathBranch",
    "path_branch_stage",
    "resolve_path_branches",
    "wrap_children",
]


def wrap_children(
    name: str,
    children: Sequence[py_trees.behaviour.Behaviour],
    body_name: str | None = None,
    as_one_act: bool = False,
) -> py_trees.behaviour.Behaviour:
    """One child runs bare; several become a Sequence so FAILURE propagates.

    The shared body shape of every gated or branched subtree, so the
    role gates and the path branches cannot disagree about it (CS-22-001).
    With *as_one_act* the body is always an
    :class:`~vultron.core.behaviors.act_transaction.ActTransaction`, so
    everything the children write commits together or not at all
    (CLP-07-015).
    """
    if as_one_act:
        return ActTransaction(
            name=body_name or f"{name}Body", children=list(children)
        )
    if len(children) == 1:
        return children[0]
    return py_trees.composites.Sequence(
        name=body_name or f"{name}Body",
        memory=False,
        children=list(children),
    )


@dataclass(frozen=True)
class OnPaths:
    """A subtree a received tree runs only on the paths it names (HP-01-038).

    Attributes:
        name: Names the branch, and so its node in a log line.
        paths: The declared paths the children run on; a strict subset of
            the tree's declaration, because a branch that names every
            declared path is not a branch.
        children: The nodes to run on those paths, in order.
        body_name: Name of the Sequence wrapping several children; defaults
            to ``{name}Body``.
    """

    name: str
    paths: frozenset[ReceivedPath]
    children: tuple[py_trees.behaviour.Behaviour, ...] = field(
        default_factory=tuple
    )
    body_name: str | None = None

    @classmethod
    def at_case_manager(
        cls,
        name: str,
        *children: py_trees.behaviour.Behaviour,
        body_name: str | None = None,
    ) -> OnPaths:
        """The branch that runs at the case's CASE_MANAGER alone."""
        return cls(
            name=name,
            paths=frozenset({ReceivedPath.CASE_MANAGER}),
            children=tuple(children),
            body_name=body_name,
        )

    @classmethod
    def off_case_manager(
        cls,
        name: str,
        *children: py_trees.behaviour.Behaviour,
        body_name: str | None = None,
    ) -> OnPaths:
        """The branch that runs on every declared path but the manager's.

        The complement of :meth:`at_case_manager`, and the replacement for
        the participant-replica gate: a receiver that holds a replica
        without the role, and one that holds no replica at all, both record
        what arrived for themselves (RSH-08-003).  The factory narrows the
        set to the paths the tree declared, so a tree that declares no
        no-case branch gets a branch on the replica path alone.
        """
        return cls(
            name=name,
            paths=frozenset(ReceivedPath) - {ReceivedPath.CASE_MANAGER},
            children=tuple(children),
            body_name=body_name,
        )


class PathBranch(py_trees.composites.Selector):
    """The Selector :func:`path_branch_stage` returns.

    A plain ``Selector`` in behaviour; the subclass names the shape so a
    reader of a built tree can tell a path branch from any other Selector
    without matching child names, and :attr:`paths` says which paths it runs
    on.  :func:`~vultron.core.behaviors.case.receive_stages.effects.ungated_nodes`
    reads :attr:`paths` to tell a manager-only branch from one that runs at a
    replica.  :attr:`branch` is the work; the first child is the skip arm.

    Only :func:`path_branch_stage` constructs one, so the type implies the
    ``CheckReceivedPathNode`` skip arm.
    """

    def __init__(
        self,
        name: str,
        paths: frozenset[ReceivedPath],
        skip_arm: py_trees.behaviour.Behaviour,
        branch: py_trees.behaviour.Behaviour,
    ) -> None:
        super().__init__(name=name, memory=False, children=[skip_arm, branch])
        self.paths = paths

    @property
    def branch(self) -> py_trees.behaviour.Behaviour:
        """The child that runs only on :attr:`paths`.

        The counterpart of
        :attr:`~vultron.core.behaviors.case.nodes.role_gates.CaseManagerGate.gated_branch`:
        a reader of a built tree asking what the branch does reads this
        rather than indexing into ``children``.
        """
        return self.children[1]


def path_branch_stage(
    where: str,
    declaration: OnPaths,
    stage: ReceivedPathNode | None,
) -> PathBranch:
    """Build the branch *declaration* asks for, reading *stage*'s answer.

    *where* names the call site in any wiring error.  The declaration's
    paths are narrowed to the tree's own declaration, so
    :meth:`OnPaths.off_case_manager` means "every declared path but the
    manager's" in each tree that uses it.

    Raises:
        VultronWiringError: the tree declared no paths, so no stage resolved
            one to read (ADR-0153, HP-01-035); the branch names no path, or
            none the tree declared, so it could never run; or it names every
            declared path, which is the tree itself rather than a branch
            (HP-01-038).
    """
    if stage is None:
        raise VultronWiringError(
            f"{where}: the {declaration.name!r} branch reads the path stage's"
            " answer, so the tree must declare its paths (ADR-0153,"
            " HP-01-035)"
        )
    if not declaration.paths:
        raise VultronWiringError(
            f"{where}: the {declaration.name!r} branch names no path, so it"
            " could never run (HP-01-038)"
        )
    if not declaration.children:
        raise VultronWiringError(
            f"{where}: the {declaration.name!r} branch holds no node, so it"
            " would read as a path the tree does something on and do nothing"
            " there (HP-01-038)"
        )
    paths = declaration.paths & stage.declared
    if not paths:
        raise VultronWiringError(
            f"{where}: the {declaration.name!r} branch runs on"
            f" {sorted(path.value for path in declaration.paths)}, none of"
            f" which the tree declares"
            f" ({sorted(path.value for path in stage.declared)}), so it"
            " could never run (HP-01-038)"
        )
    if paths == stage.declared:
        raise VultronWiringError(
            f"{where}: the {declaration.name!r} branch runs on every path the"
            " tree declares, so it is the tree's own work rather than a"
            " branch of it; pass its children directly (HP-01-038)"
        )
    skip_arm = py_trees.composites.Sequence(
        name=f"SkipOff{declaration.name}",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name=f"NotOn{declaration.name}Path",
                child=on_any_of_paths(stage, paths),
            )
        ],
    )
    return PathBranch(
        name=declaration.name,
        paths=paths,
        skip_arm=skip_arm,
        branch=wrap_children(
            declaration.name, list(declaration.children), declaration.body_name
        ),
    )


def resolve_path_branches(
    where: str,
    items: Sequence[py_trees.behaviour.Behaviour | OnPaths],
    stage: ReceivedPathNode | None,
) -> list[py_trees.behaviour.Behaviour]:
    """*items* with every :class:`OnPaths` declaration built in place.

    The one place a path branch is constructed from what a tree passed, so a
    tree's guards and its effects get the same shape and the same wiring
    errors.  Order is preserved and load-bearing: the returned list becomes
    the tree's children in the order the tree listed them, which is why
    *items* is a ``Sequence`` rather than any collection.  A guard list may
    also hold a
    :class:`~vultron.core.behaviors.case.nodes.diversion_stage.Diversion`;
    :func:`~vultron.core.behaviors.case.receive_stages.guards.precondition_guard_nodes`
    builds those first and passes the result here, so each stays at its own
    place in the list.
    """
    return [
        path_branch_stage(where, item, stage)
        if isinstance(item, OnPaths)
        else item
        for item in items
    ]
