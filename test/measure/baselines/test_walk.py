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

"""The exact indifference walk on small hand-built models (ADR-0182)."""

from fractions import Fraction
from typing import NamedTuple

import pytest

from vultron.measure.baselines.walk import (
    Ordering,
    OrderingQuery,
    Step,
    WalkNeverEndsError,
    frequency,
    implies,
    ordering,
)


class _Graph(NamedTuple):
    """A model given as ``state -> ((event, next, also), ...)``."""

    start: str
    edges: dict[str, tuple[tuple[str, str, frozenset[str]], ...]]

    @property
    def initial(self) -> str:
        return self.start

    def steps(self, state: str) -> tuple[Step[str, str], ...]:
        return tuple(
            Step(event, dest, also)
            for event, dest, also in self.edges.get(state, ())
        )


_NONE: frozenset[str] = frozenset()

# From s, a or b first, each with 1/2; then the other.
_FORK = _Graph(
    "s",
    {
        "s": (("a", "A", _NONE), ("b", "B", _NONE)),
        "A": (("b", "end", _NONE),),
        "B": (("a", "end", _NONE),),
    },
)

# From s, either loop back through t, or leave by x; leaving by y needs t.
#   s -> t (loop), s -> x-end ; t -> s (back), t -> y-end
_LOOP = _Graph(
    "s",
    {
        "s": (("go", "t", _NONE), ("x", "done", _NONE)),
        "t": (("back", "s", _NONE), ("y", "done-y", _NONE)),
    },
)


def test_an_acyclic_fork_gives_each_order_half():
    assert frequency(_FORK, ordering("a", "b")) == Fraction(1, 2)


def test_a_cycle_is_solved_exactly_not_sampled():
    # p = P(x before y) from s: p = 1/2 + 1/2 * (1/2 * p)  =>  p = 2/3.
    assert frequency(_LOOP, ordering("x", "y")) == Fraction(2, 3)


def test_an_ordering_holds_when_its_later_event_never_comes():
    # A walk leaving by y never meets x, and y ≺ x holds on it.
    assert frequency(_LOOP, ordering("y", "x")) == Fraction(1, 3)


def test_an_ordering_fails_when_its_earlier_event_never_comes():
    # "back" occurs only on walks that loop at least once (1/2 · 1/2); every
    # other walk fails back ≺ x, however it ends.
    assert frequency(_LOOP, ordering("back", "x")) == Fraction(1, 4)


def test_events_of_one_step_are_simultaneous():
    model = _Graph("s", {"s": (("a", "end", frozenset({"b"})),)})
    assert frequency(model, ordering("a", "b")) == 0
    assert frequency(model, ordering("b", "a")) == 0


def test_given_scopes_the_frequency_to_walks_meeting_it():
    # Among walks where y occurs, x never comes first.
    assert frequency(_LOOP, ordering("x", "y", given=["y"])) == 0
    assert frequency(_LOOP, ordering("go", "y", given=["y"])) == 1


def test_a_given_no_walk_meets_is_refused():
    with pytest.raises(ValueError, match="no walk"):
        frequency(_FORK, ordering("a", "b", given=["missing"]))


def test_a_walk_that_never_ends_is_refused():
    model = _Graph(
        "s",
        {
            "s": (("go", "t", _NONE), ("x", "done", _NONE)),
            "t": (("back", "u", _NONE),),
            "u": (("again", "t", _NONE),),
        },
    )
    with pytest.raises(WalkNeverEndsError):
        frequency(model, ordering("x", "go"))


def test_a_conjunction_needs_every_ordering():
    query = OrderingQuery((Ordering("a", "b"), Ordering("b", "a")))
    assert frequency(_FORK, query) == 0


def test_implies_finds_a_counterexample_or_none():
    assert implies(_LOOP, ordering("y", "x"), ordering("go", "x"))
    assert not implies(_LOOP, ordering("go", "x"), ordering("y", "x"))


def test_a_state_that_steps_to_itself_is_a_cycle():
    # From s, stay (back to s) or leave by x, each 1/2: "stay" happens on
    # every walk that stays at least once.
    model = _Graph("s", {"s": (("stay", "s", _NONE), ("x", "end", _NONE))})
    assert frequency(model, ordering("stay", "x")) == Fraction(1, 2)
    assert frequency(model, ordering("x", "stay")) == Fraction(1, 2)
