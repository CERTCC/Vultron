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

"""The interim seeder: seed a node's per-act keys with values a factory holds.

Under BTND-01-008 a node reads each per-act value from a key of the
vocabulary (:mod:`vultron.core.behaviors.act_keys`), and under BTND-01-009 no
factory takes one.  The migration moves the nodes first.  Until a node's
factory loses its parameters, the factory still holds the values at build
time, so it seeds the moved node's keys instead of passing them to its
constructor: :func:`with_act_keys` wraps the node in an :class:`ActKeyScope`,
which writes each key for the node's own tick and puts back whatever the key
held before, on every outcome (BT-17-007).

The seed is scoped to the wrapped node rather than left on the blackboard:

- Within one execution, a later sibling still reads the value an earlier node
  published, exactly as it would without the seed, so wrapping a node changes
  what no other node sees.
- Across executions, nothing is left behind for a later delivery to read
  (#5803, BT-09).

A scope publishes the keys it seeds (:meth:`ActKeyScope.published_act_keys`),
so a tree that also declares one of them seeded by the runner, or published
by a lookup node, fails the one-source check (BT-25-011).

The seeder is interim: each family's factory Task removes its calls, and the
close-out Task (#6593) deletes this module.
"""

from collections.abc import Iterator, Mapping
from types import MappingProxyType

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.act_keys import ActKey, require_act_key
from vultron.core.behaviors.blackboard_scope import (
    restore_keys,
    snapshot_keys,
)

__all__ = ["ActKeyScope", "seeded_value", "unscoped", "with_act_keys"]


class ActKeyScope(py_trees.decorators.Decorator):
    """Decorator: tick *child* with each key of *seeds* set to its value.

    Each key's previous state (absent, ``None`` or another value) is restored
    when the child's tick finishes, on every outcome: success, failure, an
    exception, or a parent that stops the tick at the child.  The seed is
    visible to the child and its descendants alone.  The decorator passes the
    child's status and reason through unchanged.

    A value is seeded as the factory holds it; its type is checked where the
    runner seeds the key from the act (BT-25-007), not here, so a tree built
    in a test from stand-in values builds as it did before the seeder.

    Args:
        child: The node whose input ports read the seeded keys.
        seeds: Each vocabulary key and the value the tree names at build
            time.
        name: Node name; defaults to the child's, so a tree reads the same
            by name whether or not a node in it is seeded.

    Raises:
        ValueError: *seeds* is empty, or a value is ``None`` or ``""``; a
            scope that seeds nothing is a composition fault, and
            :func:`with_act_keys` never builds one.
        TypeError: A key is not a key of the vocabulary (BTND-03-022).

    """

    def __init__(
        self,
        child: py_trees.behaviour.Behaviour,
        seeds: Mapping[ActKey, object],
        name: str | None = None,
    ) -> None:
        where = name or child.name
        if not seeds:
            raise ValueError(f"{where}: an ActKeyScope must seed a key")
        checked = {require_act_key(key, where): v for key, v in seeds.items()}
        empty = sorted(
            k.path for k, v in checked.items() if v is None or v == ""
        )
        if empty:
            raise ValueError(
                f"{where}: {', '.join(empty)} would be seeded with no value;"
                " with_act_keys leaves such a key unseeded (CS-08-002)"
            )
        super().__init__(name=where, child=child)
        self._seeds: Mapping[ActKey, object] = MappingProxyType(checked)

    @property
    def seeds(self) -> Mapping[ActKey, object]:
        """Each key this scope seeds, with its value (read-only)."""
        return self._seeds

    def tick(self) -> Iterator[py_trees.behaviour.Behaviour]:
        storage = py_trees.blackboard.Blackboard.storage
        saved = snapshot_keys(storage, [key.name for key in self._seeds])
        for key, value in self._seeds.items():
            storage[key.path] = value
        try:
            yield from super().tick()
        finally:
            restore_keys(storage, saved)

    def update(self) -> Status:
        self.feedback_message = self.decorated.feedback_message
        return self.decorated.status

    def published_act_keys(self) -> frozenset[ActKey]:
        """The keys this scope writes for its child's tick (BT-25-011)."""
        return frozenset(self._seeds)


def with_act_keys(
    node: py_trees.behaviour.Behaviour,
    seeds: Mapping[ActKey, object | None],
) -> py_trees.behaviour.Behaviour:
    """*node* with each key of *seeds* that has a value seeded for its tick.

    A key whose value is ``None`` or ``""`` is not seeded ("if present, then
    non-empty", CS-08-002): the node then reads what an earlier node of the
    same execution published, or its documented tick-time resolution step.
    When no key has a value, *node* comes back unwrapped.

    A node that is already an :class:`ActKeyScope` is not wrapped again: its
    seeds and *seeds* become one scope, so a seeded node always sits exactly
    one level below where an unseeded one would.

    Raises:
        ValueError: *node* already seeds a key of *seeds* with another value;
            the node would read one of two values (BT-25-011).
        TypeError: As :class:`ActKeyScope`.
    """
    present = {
        key: value
        for key, value in seeds.items()
        if value is not None and value != ""
    }
    if not present:
        return node
    if isinstance(node, ActKeyScope):
        for key, value in present.items():
            if key in node.seeds and node.seeds[key] != value:
                raise ValueError(
                    f"{node.name}: '{key.path}' is already seeded with"
                    f" {node.seeds[key]!r}, not {value!r} (BT-25-011)"
                )
        return ActKeyScope(
            node.decorated, {**node.seeds, **present}, name=node.name
        )
    return ActKeyScope(node, present)


def unscoped(
    node: py_trees.behaviour.Behaviour,
) -> py_trees.behaviour.Behaviour:
    """*node*, or the node an :class:`ActKeyScope` seeds when *node* is one.

    For code that reads a tree's shape: a seeded node sits one level below
    where an unseeded one would.
    """
    if isinstance(node, ActKeyScope):
        return node.decorated
    return node


def seeded_value(node: py_trees.behaviour.Behaviour, key: ActKey) -> object:
    """The value an :class:`ActKeyScope` directly above *node* seeds for *key*.

    ``None`` when no scope above *node* seeds *key*.  For code that reads
    which value a tree hands a node at build time.
    """
    parent = node.parent
    if isinstance(parent, ActKeyScope):
        return parent.seeds.get(key)
    return None
