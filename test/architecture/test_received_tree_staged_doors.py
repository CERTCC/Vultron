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

"""Every built received tree runs its doors before intake (CLP-10-010, ADR-0154).

Asked of the *built* trees (``_received_tree_builds``), so a nested received
tree -- the close-case tree's inner one -- is checked where it runs.  In each
:class:`~vultron.core.behaviors.case.receive_stages.tree.ReceivedActivityTree`:

- the seen-before door is a door guard, one per tree, so every resend is
  answered from its record before anything is written;
- intake is the child right after the last door guard, so a message a door
  turns away is never held in full;
- the addressee check, where the tree carries it, comes before the
  seen-before door, in ADR-0154's order;
- a tree built ``nested`` has no seen-before door and no intake of its own,
  and runs inside a tree that has both, after that tree's intake: a second
  intake would meet the record the first wrote and read a first run as a
  re-run (ADR-0154).
"""

import py_trees
import pytest

from test.architecture._received_tree_builds import built_received_trees
from vultron.core.behaviors.case.nodes.addressee import (
    ActivityAddressedToReceiverNode,
)
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.seen_before import (
    ActivityNotSeenBeforeNode,
)
from vultron.core.behaviors.case.receive_stages.tree import (
    ReceivedActivityTree,
)


def _received_trees(
    root: py_trees.behaviour.Behaviour,
) -> list[ReceivedActivityTree]:
    return [n for n in root.iterate() if isinstance(n, ReceivedActivityTree)]


def _index(tree: ReceivedActivityTree, node_type: type) -> list[int]:
    return [
        i
        for i, child in enumerate(tree.children)
        if isinstance(child, node_type)
    ]


def _enclosing_intake_ran_first(tree: ReceivedActivityTree) -> bool:
    """Whether a non-nested received tree holds *tree* after its intake."""
    child: py_trees.behaviour.Behaviour = tree
    parent = tree.parent
    while parent is not None:
        if isinstance(parent, ReceivedActivityTree) and not parent.nested:
            position = parent.children.index(child)
            intake = _index(parent, IntakeReceivedActivityNode)
            return bool(intake) and intake[0] < position
        child, parent = parent, parent.parent
    return False


def _inside_a_received_tree(tree: ReceivedActivityTree) -> bool:
    parent = tree.parent
    while parent is not None:
        if isinstance(parent, ReceivedActivityTree):
            return True
        parent = parent.parent
    return False


def _misplaced(tree: ReceivedActivityTree) -> list[str]:
    """What is out of the staged order in *tree*'s own children."""
    problems: list[str] = []
    if not tree.nested and _inside_a_received_tree(tree):
        # Its intake would meet the enclosing tree's record and read the
        # first run as a re-run (ADR-0154).
        return ["received tree inside another, not built nested"]
    seen = _index(tree, ActivityNotSeenBeforeNode)
    intake = _index(tree, IntakeReceivedActivityNode)
    addressee = _index(tree, ActivityAddressedToReceiverNode)
    doors = len(tree.door_guards)
    if tree.nested:
        if seen or intake:
            problems.append(
                f"nested tree has a seen-before door at {seen} or intake at"
                f" {intake}"
            )
        if not _enclosing_intake_ran_first(tree):
            problems.append("nested tree not after an enclosing intake")
        return problems
    if len(seen) != 1 or tree.children[seen[0]] not in tree.door_guards:
        problems.append(f"seen-before door at {seen}, not one door guard")
    if intake != [doors]:
        problems.append(f"intake at {intake}, not right after {doors} doors")
    if addressee and seen and addressee[0] > seen[0]:
        problems.append("addressee check after the seen-before door")
    return problems


@pytest.mark.spec("CLP-10-081")
@pytest.mark.spec("CLP-10-010")
@pytest.mark.spec("CLP-10-017")
def test_every_received_tree_runs_its_doors_before_intake() -> None:
    trees = built_received_trees()
    assert trees, "no received trees were built"
    offenders = {
        f"{site}:{tree.name}": problems
        for site, root in trees.items()
        for tree in _received_trees(root)
        if (problems := _misplaced(tree))
    }
    assert offenders == {}, offenders


@pytest.mark.spec("CLP-10-010")
def test_the_check_reports_a_tree_built_out_of_order() -> None:
    """A control: intake ahead of the doors is reported (no vacuous pass)."""
    door = ActivityNotSeenBeforeNode(label="Control")
    intake = IntakeReceivedActivityNode()
    tree = ReceivedActivityTree(
        name="Control", children=[intake, door], door_guards=[door]
    )
    assert _misplaced(tree) == ["intake at [0], not right after 1 doors"]


@pytest.mark.spec("CLP-10-081")
@pytest.mark.spec("CLP-10-010")
def test_the_check_reports_a_tree_nested_without_the_flag() -> None:
    """A control: an inner tree that forgot ``nested=True`` is reported."""
    inner_door = ActivityNotSeenBeforeNode(label="Inner")
    inner = ReceivedActivityTree(
        name="Inner",
        children=[inner_door, IntakeReceivedActivityNode()],
        door_guards=[inner_door],
    )
    door = ActivityNotSeenBeforeNode(label="Outer")
    ReceivedActivityTree(
        name="Outer",
        children=[door, IntakeReceivedActivityNode(), inner],
        door_guards=[door],
    )
    assert _misplaced(inner) == [
        "received tree inside another, not built nested"
    ]


@pytest.mark.spec("CLP-10-010")
def test_the_check_reports_a_nested_tree_with_its_own_intake() -> None:
    """A control: a nested tree that records the message again is reported."""
    intake = IntakeReceivedActivityNode()
    nested = ReceivedActivityTree(
        name="Inner", children=[intake], door_guards=[], nested=True
    )
    assert _misplaced(nested) == [
        "nested tree has a seen-before door at [] or intake at [0]",
        "nested tree not after an enclosing intake",
    ]
