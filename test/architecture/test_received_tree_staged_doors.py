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
  seen-before door, in ADR-0154's order.
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


def _misplaced(tree: ReceivedActivityTree) -> list[str]:
    """What is out of the staged order in *tree*'s own children."""
    problems: list[str] = []
    seen = _index(tree, ActivityNotSeenBeforeNode)
    intake = _index(tree, IntakeReceivedActivityNode)
    addressee = _index(tree, ActivityAddressedToReceiverNode)
    doors = len(tree.door_guards)
    if len(seen) != 1 or tree.children[seen[0]] not in tree.door_guards:
        problems.append(f"seen-before door at {seen}, not one door guard")
    if intake != [doors]:
        problems.append(f"intake at {intake}, not right after {doors} doors")
    if addressee and seen and addressee[0] > seen[0]:
        problems.append("addressee check after the seen-before door")
    return problems


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
