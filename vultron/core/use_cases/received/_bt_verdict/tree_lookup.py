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

"""Find nodes in a finished received-side BT run and read their status.

The lookups every verdict reader shares: a node by type or by name, whether
any node of a type failed or succeeded, the door guards' record, the path
the path door stage resolved, a taken diversion, and the run's failure
reason (BT-13-001).
"""

from typing import Protocol, TypeVar

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.case.nodes.diversion_stage import DiversionStage
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
    ReceivedPathNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
)
from vultron.errors import VultronWiringError

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


def received_path(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
) -> ReceivedPath | None:
    """The path the tree's path door stage resolved for this receiver.

    ``None`` for a tree that declared no paths, and for one whose stage did
    not run.  This is how a handler reads which of the three paths it is on
    (ADR-0153): the answer comes from the one role question the stage asked,
    never from inferring "not the manager" out of a failed gate anywhere in
    the tree (:func:`not_case_manager`, which the migration retires).
    """
    stage = find_node(tree, ReceivedPathNode)
    return None if stage is None else stage.resolved_path


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
