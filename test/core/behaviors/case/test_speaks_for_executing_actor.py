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

"""BT-17-008's second arm, as the factory's walk reads it.

The first arm is a shape — a ``CaseManagerGate``, or a ``PathBranch`` naming
the manager path alone — and ``ungated_emitters`` has always read it. The
second arm cannot be read from a shape, because any leaf could be the check
that the executing actor is the actor the emit speaks for, so the leaf says
so by carrying ``SpeaksForExecutingActor``.

What is pinned here is the whole of what the marker buys:

1. The two placements that bound an emit, which are the two ways one node in
   a behaviour tree decides whether later ones run: ahead of the emit in a
   ``Sequence``, and as the inverted first arm of a ``Selector``.
2. The shapes that do **not** bound it — an unmarked leaf, a marked leaf
   *after* the emit, a marked leaf in a ``Selector`` arm that is not the
   first, and a bare marked leaf as a ``Selector``'s first arm, where
   failing admits the next arm rather than skipping it.
3. That ``ungated_nodes`` does not read the marker at all: the state-write
   ratchet asks RSH-08-003's question, which an identity check does not
   answer.
4. That the three live leaves carry it, and that an emit they bound keeps
   its tree buildable without an exemption — the positive control that
   outlives the three exemptions #5044 retired, so a marker silently
   dropped from one of them fails here.
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.delegation import IsRoleOfferTargetNode
from vultron.core.behaviors.case.receive_stages.effects import (
    ungated_emitters,
    ungated_nodes,
)
from vultron.core.behaviors.embargo.nodes.invite_answer import (
    CanAnswerEmbargoInviteNode,
)
from vultron.core.behaviors.embargo.nodes.pxa_refusal import (
    ReceiverIsInviteeNode,
)
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.speaks_for_executing_actor import (
    SpeaksForExecutingActor,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable


class _Leaf(py_trees.behaviour.Behaviour):
    def __init__(self, name: str) -> None:
        super().__init__(name=name)

    def update(self) -> Status:
        return Status.SUCCESS


class _Emit(_Leaf, EmitCapable):
    """A stand-in emit node: carries the marker, emits nothing."""


class _Write(_Leaf, StateWriteCapable):
    """A stand-in state writer: carries the marker, writes nothing."""


class _Subject(_Leaf, SpeaksForExecutingActor):
    """A stand-in identity check: admits the executing actor alone."""


def _seq(
    *children: py_trees.behaviour.Behaviour,
) -> py_trees.composites.Sequence:
    return py_trees.composites.Sequence(
        name="Seq", memory=False, children=list(children)
    )


def _sel(
    *children: py_trees.behaviour.Behaviour,
) -> py_trees.composites.Selector:
    return py_trees.composites.Selector(
        name="Sel", memory=False, children=list(children)
    )


def _inverted(
    child: py_trees.behaviour.Behaviour,
) -> py_trees.behaviour.Behaviour:
    return py_trees.decorators.Inverter(name="NotTheSubject", child=child)


@pytest.mark.spec("BT-17-008")
def test_a_sequence_guard_bounds_the_emits_after_it() -> None:
    """The guard runs first, so the emit runs only where it succeeded."""
    emit = _Emit("Answer")

    assert ungated_emitters([_seq(_Subject("IsTheSubject"), emit)]) == []


@pytest.mark.spec("BT-17-008")
def test_the_effect_list_a_tree_passes_is_read_as_a_sequence() -> None:
    """The factory runs ``replica_effects`` in order, so the same rule holds.

    ``check_replica_effects`` hands the walk the list itself rather than the
    composite the factory later makes of it, so a guard at the top of that
    list has to bound what follows it (CLP-10-010).
    """
    roots: list[py_trees.behaviour.Behaviour] = [
        _Subject("IsTheSubject"),
        _Emit("Answer"),
    ]

    assert ungated_emitters(roots) == []


@pytest.mark.spec("BT-17-008")
def test_an_inverted_first_selector_arm_bounds_the_later_arms() -> None:
    """The skip shape: every later arm runs only where the guard succeeded."""
    emit = _Emit("Answer")

    assert (
        ungated_emitters([_sel(_inverted(_Subject("CanAnswer")), emit)]) == []
    )


@pytest.mark.spec("BT-17-008")
def test_an_inverted_arm_wrapped_in_a_sequence_still_bounds_them() -> None:
    """The CASE_MANAGER gate's own spelling of its skip arm."""
    emit = _Emit("Answer")
    skip = _seq(_inverted(_Subject("CanAnswer")))

    assert ungated_emitters([_sel(skip, emit)]) == []


@pytest.mark.spec("BT-17-008")
def test_an_unmarked_leaf_bounds_nothing() -> None:
    """A guard that checks something else is not the second arm (#2667)."""
    emit = _Emit("Answer")

    assert ungated_emitters([_seq(_Leaf("HoldsTheCase"), emit)]) == [emit]


@pytest.mark.spec("BT-17-008")
def test_a_guard_after_the_emit_bounds_nothing() -> None:
    """Order is the whole of the sequence placement: the emit ran first."""
    emit = _Emit("Answer")

    assert ungated_emitters([_seq(emit, _Subject("IsTheSubject"))]) == [emit]


@pytest.mark.spec("BT-17-008")
def test_a_guard_in_a_later_selector_arm_bounds_nothing() -> None:
    """Only the first arm decides whether the Selector reaches the rest."""
    emit = _Emit("Answer")
    root = _sel(_Leaf("FirstArm"), _inverted(_Subject("CanAnswer")), emit)

    assert ungated_emitters([root]) == [emit]


@pytest.mark.spec("BT-17-008")
def test_a_bare_first_selector_arm_bounds_nothing() -> None:
    """Uninverted, the guard's FAILURE *admits* the next arm, not skips it.

    A ``Selector`` tries its next child when one fails, so a bare identity
    check as the first arm lets the emit run at every *other* actor — the
    opposite of a guard. Reading it as one would exempt the emit that most
    needs reporting.
    """
    emit = _Emit("Answer")

    assert ungated_emitters([_sel(_Subject("CanAnswer"), emit)]) == [emit]


@pytest.mark.spec("RSH-08-003")
def test_the_state_write_walk_does_not_read_the_marker() -> None:
    """An identity check does not answer RSH-08-003's question.

    A received-side write belongs to the case's CASE_MANAGER whoever the
    write is *about*, so the marker must not quietly exempt one.
    """
    write = _Write("Record")

    assert ungated_nodes(
        [_seq(_Subject("IsTheSubject"), write)], StateWriteCapable
    ) == [write]


@pytest.mark.spec("BT-17-008")
@pytest.mark.parametrize(
    "node_class",
    [ReceiverIsInviteeNode, CanAnswerEmbargoInviteNode, IsRoleOfferTargetNode],
    ids=lambda cls: cls.__name__,
)
def test_each_live_identity_check_carries_the_marker(
    node_class: type,
) -> None:
    """The positive control for the three exemptions #5044 retired.

    Each of those trees kept its emit and dropped its recorded waiver,
    because the leaf in front of the emit is the second arm. Dropping the
    marker from one of them would silently un-guard that emit, so the live
    classes are pinned here rather than only in the trees that use them.
    """
    assert issubclass(node_class, SpeaksForExecutingActor)
