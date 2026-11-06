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

"""Seed a node's ``/case_id`` port with a case a tree knows at build time.

A node that some tree hands its case only at tick time reads ``case_id`` from
its declared ``/case_id`` input port in every tree, never also from a
constructor argument (BTND-01-006).  A tree that *does* know the case when it
is built seeds that port instead: :func:`with_case_id` wraps the node in a
:class:`CaseIdScope`, which writes the case to ``/case_id`` for the node's own
tick and puts back whatever the key held before (BTND-10-005, ADR-0089).

The seed is scoped to the wrapped node rather than left on the blackboard for
two reasons:

- Within one execution, a later sibling still reads the ``/case_id`` an
  earlier node published, exactly as it would without the seed, so wrapping a
  node changes what no other node sees.
- Across executions, nothing is left behind for a later delivery to resolve
  (#5803, BT-09).  ``BTBridge.execute_with_setup`` scopes ``/case_id`` per
  execution as well; the wrapper does not rely on it.
"""

from collections.abc import Iterator

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.blackboard_scope import (
    restore_keys,
    snapshot_keys,
)

__all__ = ["CaseIdScope", "seeded_case_id", "unscoped", "with_case_id"]

#: The bare name of the port key every ``case_id``-reading node remaps to.
_CASE_ID_KEY = "case_id"


class CaseIdScope(py_trees.decorators.Decorator):
    """Decorator: tick *child* with ``/case_id`` seeded to *case_id*.

    The key's previous state — absent, ``None`` or another case — is restored
    when the child's tick finishes, on every outcome, so the seed is visible
    to the child and its descendants alone.  The decorator passes the child's
    status through unchanged.

    Args:
        child: The node whose ``/case_id`` input port is seeded.
        case_id: The case the tree names at build time.
        name: Node name; defaults to the child's, so a tree reads the same
            by name whether or not a node in it is seeded.
    """

    def __init__(
        self,
        child: py_trees.behaviour.Behaviour,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or child.name, child=child)
        self.case_id = case_id

    def tick(self) -> Iterator[py_trees.behaviour.Behaviour]:
        storage = py_trees.blackboard.Blackboard.storage
        saved = snapshot_keys(storage, [_CASE_ID_KEY])
        storage[f"/{_CASE_ID_KEY}"] = self.case_id
        try:
            yield from super().tick()
        finally:
            restore_keys(storage, saved)

    def update(self) -> Status:
        self.feedback_message = self.decorated.feedback_message
        return self.decorated.status


def with_case_id(
    node: py_trees.behaviour.Behaviour, case_id: str | None
) -> py_trees.behaviour.Behaviour:
    """*node* with its ``/case_id`` port seeded to *case_id*, when there is one.

    A tree that names no case at build time passes ``None`` (or ``""``) and
    gets *node* back unwrapped: the node then reads the ``/case_id`` an
    earlier node of the same execution published, or its documented
    tick-time resolution step.
    """
    if not case_id:
        return node
    return CaseIdScope(node, case_id)


def unscoped(
    node: py_trees.behaviour.Behaviour,
) -> py_trees.behaviour.Behaviour:
    """*node*, or the node a :class:`CaseIdScope` seeds when *node* is one.

    For code that reads a tree's shape: a seeded node sits one level below
    where an unseeded one would.
    """
    if isinstance(node, CaseIdScope):
        return node.decorated
    return node


def seeded_case_id(node: py_trees.behaviour.Behaviour) -> str | None:
    """The case a :class:`CaseIdScope` directly above *node* seeds, or ``None``.

    For code that reads which case a tree hands a node at build time.
    """
    parent = node.parent
    if isinstance(parent, CaseIdScope):
        return parent.case_id
    return None
