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

"""A sender door's FAILURE is the received tree's refusal, not a branch.

``SenderEntitlementConditionNode._refuse_by_placement`` decides WARNING
against DEBUG by asking ``failure_is_the_refusal(node)``, which walks the
node's parents and answers ``False`` at the first Selector with a later
sibling (SL-03-002, #5460).  Inside the guard that is the point: an any-of
side's earlier arms can be overruled by a later kind.  *Above* the guard it
would be a defect — every real refusal would silently drop to DEBUG, and
nothing would catch it, because the demo tests' ``expect_no_sender_refusals``
only sees a WARNING that should not be there, never a missing one.

``sender_guard_refused`` rests on the same premise from the other side: it
reads the guard as one child of the tree's root Sequence (HP-01-025).  This
ratchet pins the premise for both.

Asked of the *built* trees rather than of the factories' source, so a guard
placed by a helper or a nested factory is seen exactly as it runs, and asked
through ``ReceivedActivityTree.door_guards`` rather than by matching a node or
composite name, so no subject is lost to a rename (#5535).  A sender check
that selects an *effect* after admission is deliberately out of scope: it is
not a door, and its FAILURE is not the tree's answer.

A door counts as a subject two ways, because either is enough to make the
level depend on the placement.  It carries the composer's own mark
(``is_composed_sender_guard``), whatever checks are inside it — a rule naming
one kind whose check is not a ``SenderEntitlementConditionNode``, such as
``PARTICIPANT``, composes a door of exactly that shape (#5786).  Or it holds
such a check without being a composed guard, which is the closed-sender door
with its Case Owner arm.
"""

import py_trees
import pytest

from test.architecture._received_tree_builds import built_received_trees
from vultron.core.behaviors.case.receive_stages.tree import (
    ReceivedActivityTree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementConditionNode,
    failure_is_the_refusal,
)
from vultron.core.behaviors.sender_guard import is_composed_sender_guard


def _holds_a_sender_check(node: py_trees.behaviour.Behaviour) -> bool:
    """*node* is, or encloses, a sender-entitlement check."""
    return any(
        isinstance(found, SenderEntitlementConditionNode)
        for found in node.iterate()
    )


def _judges_the_sender(node: py_trees.behaviour.Behaviour) -> bool:
    """*node* is a door whose FAILURE's log level is read from its placement."""
    return is_composed_sender_guard(node) or _holds_a_sender_check(node)


def _sender_doors(
    tree: ReceivedActivityTree,
) -> list[py_trees.behaviour.Behaviour]:
    """The tree's door guards that judge the sender's standing."""
    return [door for door in tree.door_guards if _judges_the_sender(door)]


@pytest.mark.spec("SL-03-002", "HP-01-025")
def test_every_received_tree_places_its_sender_door_as_the_refusal() -> None:
    """Nothing the factory puts above a sender door can overrule its FAILURE.

    If anything could — a Selector with a later sibling, or a decorator —
    then the door's refusal would be branch selection, and the level the
    check logs it at would be DEBUG for a sender the tree really refuses.
    """
    offenders: dict[str, list[str]] = {}
    with_doors: list[str] = []
    for (module, factory), tree in sorted(built_received_trees().items()):
        site = f"{module}:{factory}"
        assert isinstance(tree, ReceivedActivityTree), (
            f"{site}: built a {type(tree).__name__}, so its door guards"
            " cannot be read; extend this ratchet rather than skip it"
        )
        doors = _sender_doors(tree)
        if doors:
            with_doors.append(site)
        overruled = sorted(
            door.name for door in doors if not failure_is_the_refusal(door)
        )
        if overruled:
            offenders[site] = overruled

    assert with_doors, (
        "no built received tree has a door guard holding a sender check, so"
        " this ratchet proved nothing; the walk or the corpus is broken"
    )
    assert offenders == {}, (
        "a received tree places a sender door where something above it can"
        " overrule the door's FAILURE, so a sender the tree refuses would be"
        f" logged at DEBUG (SL-03-002): {offenders}"
    )
