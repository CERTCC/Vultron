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

"""No handling-tree stage reads what a door stage left in memory (ADR-0154).

ADR-0154 draws the received stage boundaries at arrival, the doors, waiting,
the handling tree and the outcome, and says a stage reads only the record and
the store, never what an earlier stage left in memory.  The doors are outside
the handling tree, so a node after them that reads a door's in-memory answer
breaks the rule: a re-run that starts at the handling tree, or a door run as
its own stage, would find that answer missing or stale.

Asked of every *built* received tree (``_received_tree_builds``), so a node
reached through a helper or a closure is seen as it runs.  In each
non-nested :class:`ReceivedActivityTree`, the door stage is every node under
its ``door_guards``, and every other node is in the handling tree.  Two
shapes carry a door's in-memory state across that boundary, and both are
keyed on the shape, never on a class name:

1. **A reference.**  A handling node holds a door node in an attribute, a
   collection in one, a bound method of one, or a callable's closure: the
   ``lambda: seen_door.rerun`` the seen-before door's retired ``rerun`` flag
   was read through.
2. **A blackboard key.**  A handling node reads a key whose last writer, in
   tick order, is a door node.  A ``CaseIdScope`` seeds ``/case_id`` for its
   own subtree, so a read inside one is the scope's.

The one reference pinned is the path answer, with its ground and its owner
(:data:`PATH_ANSWER_READS`), held to equality, so a new one is a decision.

Two boundaries outside the handling tree are not asked here, because their
reads are their sanctioned inputs: a door reads the delivery itself (the
event on ``/activity``), which arrival hands over, not state a stage wrote;
and the outcome stage reads only the handler's result, which CLP-10-073 names
as its input and ``test_received_outcome_stage.py`` pins.
"""

import functools
import logging
import types
from collections.abc import Iterator

import py_trees
import pytest

from test.architecture._received_tree_builds import built_received_trees
from vultron.core.behaviors.case.receive_stages.tree import (
    ReceivedActivityTree,
)
from vultron.core.behaviors.case_id_scope import CaseIdScope

_Finding = tuple[str, str, str]
"""(handling node class, what it reads through, door node class)."""

#: Objects whose fields are no node's state: classes, modules, functions
#: (a closure is walked by its cells) and loggers.
_NOT_PLAIN = (type, types.ModuleType, types.FunctionType, logging.Logger)

#: Attributes that are the tree's own structure, not a node's state.
_STRUCTURE = frozenset(
    {"parent", "children", "decorated", "current_child", "_current_child"}
)

# owner: #6003 (whether ADR-0154's rule admits this read)
#: The one door-to-handling read pinned, and why it differs from the retired
#: ``rerun`` flag.  ``rerun`` recorded history ("this run is a re-run") that
#: only memory knew and a restart lost.  The path answer is derived: the path
#: stage computes it again from the store on every run, so a restart loses
#: nothing.  The read is load-bearing too: the path is decided once, at the
#: door, before the act's own writes, and an act that changes who the
#: CASE_MANAGER is would make a branch that asked again diverge from the door
#: (HP-01-036, ADR-0153).  #6003 puts the conflict with ADR-0154 to the
#: maintainer.
PATH_ANSWER_READS: frozenset[_Finding] = frozenset(
    {("CheckReceivedPathNode", "stage", "ReceivedPathNode")}
)


def _nodes_in(value: object, depth: int = 0) -> Iterator[object]:
    """Every BT node *value* holds, reached through collections or closures."""
    if isinstance(value, py_trees.behaviour.Behaviour):
        yield value
        return
    if depth > 3:
        return
    for item in _held_by(value):
        yield from _nodes_in(item, depth + 1)


def _held_by(value: object) -> list[object]:
    """What *value* holds: its items, its bound ``self``, a partial's
    function and arguments, its closure cells and a plain object's fields."""
    if isinstance(value, (list, tuple, set, frozenset)):
        return list(value)
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, types.MethodType):
        return [value.__self__]
    if isinstance(value, functools.partial):
        return [value.func, *value.args, *value.keywords.values()]
    held: list[object] = []
    for cell in getattr(value, "__closure__", None) or ():
        try:
            held.append(cell.cell_contents)
        except ValueError:  # an empty cell
            continue
    if not isinstance(value, _NOT_PLAIN) and hasattr(value, "__dict__"):
        held.extend(vars(value).values())
    return held


def _references(node: py_trees.behaviour.Behaviour) -> Iterator[tuple]:
    for attr, value in vars(node).items():
        if attr in _STRUCTURE:
            continue
        for held in _nodes_in(value):
            yield attr, held


def _received_trees(
    root: py_trees.behaviour.Behaviour,
) -> list[ReceivedActivityTree]:
    return [
        n
        for n in root.iterate()
        if isinstance(n, ReceivedActivityTree) and not n.nested
    ]


def _door_ids(tree: ReceivedActivityTree) -> set[int]:
    return {id(n) for door in tree.door_guards for n in door.iterate()}


def reference_findings(tree: ReceivedActivityTree) -> set[_Finding]:
    """Handling nodes of *tree* that hold a door node of *tree*."""
    doors = _door_ids(tree)
    return {
        (type(node).__name__, attr, type(held).__name__)
        for node in tree.iterate()
        # The tree itself names its doors: it is the stages' container,
        # not a stage.
        if id(node) not in doors and not isinstance(node, ReceivedActivityTree)
        for attr, held in _references(node)
        if id(held) in doors
    }


def _keys(node: py_trees.behaviour.Behaviour, *, written: bool) -> set[str]:
    keys: set[str] = set()
    for client in getattr(node, "blackboards", []):
        keys |= (client.write | client.exclusive) if written else client.read
    return keys


def key_findings(tree: ReceivedActivityTree) -> set[_Finding]:
    """Handling nodes of *tree* that read a key a door node wrote last."""
    doors = _door_ids(tree)
    found: set[_Finding] = set()

    def walk(
        node: py_trees.behaviour.Behaviour,
        last: dict[str, py_trees.behaviour.Behaviour],
    ) -> None:
        if id(node) not in doors:
            for key in _keys(node, written=False):
                writer = last.get(key)
                if writer is not None and id(writer) in doors:
                    found.add(
                        (type(node).__name__, key, type(writer).__name__)
                    )
        for key in _keys(node, written=True):
            last[key] = node
        if isinstance(node, CaseIdScope):
            scoped = dict(last)
            scoped["/case_id"] = node
            for child in node.children:
                walk(child, scoped)
            return
        for child in node.children:
            walk(child, last)

    walk(tree, {})
    return found


@pytest.fixture(scope="module")
def set_up_trees() -> dict[tuple[str, str], py_trees.behaviour.Behaviour]:
    """Every received tree, freshly built and set up, so its keys are known.

    A fresh build, so setting the nodes up does not touch the shared corpus
    the other ratchets read.
    """
    trees = built_received_trees.__wrapped__()
    for root in trees.values():
        for node in root.iterate():
            node.setup()
    return trees


@pytest.mark.spec("CLP-10-082")
@pytest.mark.spec("CLP-10-073")
@pytest.mark.spec("CLP-10-074")
def test_no_handling_node_holds_a_door_node(set_up_trees) -> None:
    found = {
        finding: site
        for site, root in set_up_trees.items()
        for tree in _received_trees(root)
        for finding in reference_findings(tree)
    }
    assert set(found) == PATH_ANSWER_READS, (
        "a handling-tree node reads a door's in-memory state; read the"
        " record or the store instead (ADR-0154): "
        f"{sorted(set(found) - PATH_ANSWER_READS)}; no longer found:"
        f" {sorted(PATH_ANSWER_READS - set(found))}"
    )


@pytest.mark.spec("CLP-10-082")
@pytest.mark.spec("CLP-10-073")
@pytest.mark.spec("CLP-10-074")
def test_no_handling_node_reads_a_key_a_door_wrote(set_up_trees) -> None:
    keys_seen = {
        key
        for root in set_up_trees.values()
        for node in root.iterate()
        for key in _keys(node, written=False)
    }
    # Non-vacuous: the trees were set up, so their nodes' keys are known.
    assert "/case_id" in keys_seen and "/activity" in keys_seen
    found = {
        (site, finding)
        for site, root in set_up_trees.items()
        for tree in _received_trees(root)
        for finding in key_findings(tree)
    }
    assert found == set(), sorted(found)


class _Leaf(py_trees.behaviour.Behaviour):
    def update(self) -> py_trees.common.Status:
        return py_trees.common.Status.SUCCESS


class _Door(_Leaf):
    """A door that keeps an answer in memory and publishes it."""

    def __init__(self) -> None:
        super().__init__(name="Door")
        self.rerun = False
        self.client = self.attach_blackboard_client(name="Door")
        self.client.register_key(
            key="/door_answer", access=py_trees.common.Access.WRITE
        )


class _Reader(_Leaf):
    """A handling node that asks a door's answer through a closure."""

    def __init__(self, is_rerun: object) -> None:
        super().__init__(name="Reader")
        self.is_rerun = is_rerun


class _KeyReader(_Leaf):
    def __init__(self) -> None:
        super().__init__(name="KeyReader")
        self.client = self.attach_blackboard_client(name="KeyReader")
        self.client.register_key(
            key="/door_answer", access=py_trees.common.Access.READ
        )


def _planted(*handling: py_trees.behaviour.Behaviour) -> ReceivedActivityTree:
    door = handling[0] if isinstance(handling[0], _Door) else _Door()
    rest = [n for n in handling if n is not door]
    return ReceivedActivityTree(
        name="Planted", children=[door, *rest], door_guards=[door]
    )


def test_the_retired_rerun_flag_is_found() -> None:
    """A control: the shape the seen-before door's ``rerun`` flag had."""
    door = _Door()
    tree = _planted(door, _Reader(is_rerun=lambda: door.rerun))

    assert reference_findings(tree) == {("_Reader", "is_rerun", "_Door")}


def test_a_held_door_and_a_door_in_a_list_are_found() -> None:
    door = _Door()
    tree = _planted(door, _Reader(is_rerun=door), _Reader(is_rerun=[door]))

    assert reference_findings(tree) == {("_Reader", "is_rerun", "_Door")}


def test_a_key_a_door_wrote_is_found() -> None:
    door = _Door()
    tree = _planted(door, _KeyReader())

    assert key_findings(tree) == {("_KeyReader", "/door_answer", "_Door")}


def test_a_door_in_a_partial_or_a_plain_object_is_found() -> None:
    door = _Door()
    tree = _planted(
        door,
        _Reader(is_rerun=functools.partial(getattr, door, "rerun")),
        _Reader(is_rerun=types.SimpleNamespace(answer=door)),
    )

    assert reference_findings(tree) == {("_Reader", "is_rerun", "_Door")}


def test_a_node_reading_the_store_is_not_found() -> None:
    """A reader that holds no door and reads no door's key passes."""
    tree = _planted(_Door(), _Reader(is_rerun=lambda: False))

    assert reference_findings(tree) == set()
    assert key_findings(tree) == set()
