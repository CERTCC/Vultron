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

"""Compose a sender guard the way the receive-tree factory does.

The factory feeds the guard a path stage, and the stage, not the guard, asks
whether the receiver manages the case (HP-01-036).  A test that composes a
guard in isolation does the same: :func:`staged_sender_guard` builds it from
a real :class:`ReceivedPathNode`, and :func:`guard_tree` runs that stage
ahead of the guard, so the store under test decides the receiver's path and
the test never names the side it pins.
"""

from collections.abc import Collection

import py_trees

from vultron.core.behaviors.case.nodes.received_path import (
    CheckReceivedPathNode,
    ReceivedPath,
    ReceivedPathNode,
    declared_paths,
)
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    SenderContext,
    compose_sender_guard,
)

#: The paths an ordinary case tree declares: the manager and the replica.
IN_CASE_PATHS = frozenset(
    {ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA}
)

#: The path of a tree whose receiver holds no case yet.
NO_CASE_PATHS = frozenset({ReceivedPath.NO_CASE})


def path_stage(
    paths: Collection[ReceivedPath] = IN_CASE_PATHS,
) -> ReceivedPathNode:
    """A path stage declaring *paths*, as the factory builds one."""
    return ReceivedPathNode(declared=declared_paths(paths), label="test")


def staged_sender_guard(
    rule: SenderRule,
    ctx: SenderContext,
    paths: Collection[ReceivedPath] = IN_CASE_PATHS,
) -> py_trees.behaviour.Behaviour | None:
    """The guard *rule* composes for *ctx* in a tree declaring *paths*."""
    return compose_sender_guard(rule, ctx, path_stage(paths))


def _stage_of(guard: py_trees.behaviour.Behaviour) -> ReceivedPathNode | None:
    """The path stage *guard*'s side arms read, if it has any."""
    for node in guard.iterate():
        if isinstance(node, CheckReceivedPathNode):
            return node.stage
    return None


def guard_tree(
    guard: py_trees.behaviour.Behaviour, case_id: str | None
) -> py_trees.behaviour.Behaviour:
    """*guard*, preceded by the stage it reads, ready to run.

    A guard with one side reads no path and runs alone.  One with side arms
    runs after its stage, seeded with *case_id* the way the factory seeds it
    (BTND-01-006), so the stage resolves the receiver's path from the store.
    """
    stage = _stage_of(guard)
    if stage is None:
        return guard
    return py_trees.composites.Sequence(
        name="PathStageThenSenderGuard",
        memory=False,
        children=[with_case_id(stage, case_id), guard],
    )
