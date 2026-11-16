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

from collections.abc import Callable
from fractions import Fraction
from typing import NamedTuple

import pytest

import vultron.measure.baselines.walk as walk_module
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.baselines.joint import (
    ONE_VENDOR_MODEL,
    EmbargoEnd,
    Event,
    EventKind,
    JointState,
    VendorPath,
)
from vultron.measure.baselines.walk import (
    ChanceReading,
    ChanceValues,
    Ordering,
    OrderingQuery,
    Step,
    WalkNeverEndsError,
    WalkPrefix,
    difference,
    expected_outcome,
    find_step,
    frequency,
    implies,
    ordering,
    reachable_ends,
    replay,
    take_step,
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


def test_values_from_the_start_are_the_frequency() -> None:
    queries: list[OrderingQuery[str]] = [
        ordering("x", "y"),
        ordering("y", "x"),
        ordering("back", "x"),
    ]
    for query in queries:
        values = ChanceValues(_LOOP, query)
        assert values.at(WalkPrefix("s")) == frequency(_LOOP, query)


def test_a_value_from_inside_a_cycle_is_solved_there():
    # From t: back to s (then 2/3 as from the start) or y, each 1/2.
    values = ChanceValues(_LOOP, ordering("x", "y"))
    assert values.at(replay(_LOOP, ["go"])) == Fraction(1, 3)


# From s, loop with t or leave to u; from u, loop with w or end by y.
#   s <-> t, s -> u ; u <-> w, u -> y-end
_TWO_CYCLES = _Graph(
    "s",
    {
        "s": (("go", "t", _NONE), ("x", "u", _NONE)),
        "t": (("back", "s", _NONE), ("y", "done", _NONE)),
        "u": (("on", "w", _NONE), ("y", "done", _NONE)),
        "w": (("off", "u", _NONE), ("x", "done", _NONE)),
    },
)


def test_solving_from_mid_walk_first_leaves_the_start_value_exact() -> None:
    cases: list[tuple[_Graph, list[str], OrderingQuery[str]]] = [
        (_LOOP, ["go"], ordering("x", "y")),
        (_FORK, ["a"], ordering("a", "b")),
        # u's cycle is solved first; s's cycle then exits into it.
        (_TWO_CYCLES, ["x"], ordering("x", "y")),
    ]
    for model, events, query in cases:
        values = ChanceValues(model, query)
        values.at(replay(model, events))
        assert values.at(WalkPrefix(model.initial)) == frequency(model, query)


def test_a_cycle_whose_exit_was_solved_earlier_reads_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    starts: list[object] = []
    search: Callable[..., list[list[object]]] = walk_module._strongly_connected

    def counting(
        start: object, successors: Callable[[object], list[object]]
    ) -> list[list[object]]:
        components = search(start, successors)
        starts.append(start)
        # The second search stops at the solved u: w, inside u's cycle,
        # is never reached again.
        if len(starts) == 2:
            reached = {
                n.state
                for c in components
                for n in c
                if isinstance(n, walk_module._Node)
            }
            assert "u" in reached
            assert "w" not in reached
        return components

    monkeypatch.setattr(walk_module, "_strongly_connected", counting)
    values = ChanceValues(_TWO_CYCLES, ordering("x", "y"))
    # From u: y ends at once (x met first, so 1), or into w, whose x ends
    # it (1) — every walk from u meets x ≺ y.
    assert values.at(replay(_TWO_CYCLES, ["x"])) == 1
    from_start = values.at(WalkPrefix("s"))
    assert len(starts) == 2  # u first, then s
    assert from_start == frequency(_TWO_CYCLES, ordering("x", "y"))


def test_a_value_reads_what_the_history_already_settled():
    # Both walks stand at "end"; only the order the history took differs.
    values = ChanceValues(_FORK, ordering("a", "b"))
    assert values.at(replay(_FORK, ["a", "b"])) == 1
    assert values.at(replay(_FORK, ["b", "a"])) == 0
    assert values.at(replay(_FORK, ["a"])) == 1


def test_an_ended_walk_has_its_own_outcome_or_none_outside_its_scope():
    assert (
        ChanceValues(_LOOP, ordering("x", "y")).at(replay(_LOOP, ["x"])) == 1
    )
    scoped = ChanceValues(_LOOP, ordering("x", "y", given=["y"]))
    assert scoped.at(replay(_LOOP, ["x"])) is None
    assert scoped.at(replay(_LOOP, ["go", "y"])) == 0


def test_a_steps_change_is_the_value_after_minus_the_value_before():
    values = ChanceValues(_LOOP, ordering("x", "y"))
    start = WalkPrefix("s")
    assert values.change(start, "x") == 1 - Fraction(2, 3)
    assert values.change(start, "go") == Fraction(1, 3) - Fraction(2, 3)


def test_a_change_is_none_where_a_value_is_undefined():
    scoped = ChanceValues(_LOOP, ordering("x", "y", given=["y"]))
    assert scoped.change(WalkPrefix("s"), "x") is None
    assert difference(Fraction(1), None) is None
    assert difference(None, Fraction(1)) is None


def test_values_are_kept_between_lookups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    searches: list[object] = []
    search: Callable[..., list[list[object]]] = walk_module._strongly_connected

    def counting(
        start: object, successors: Callable[[object], list[object]]
    ) -> list[list[object]]:
        searches.append(start)
        return search(start, successors)

    monkeypatch.setattr(walk_module, "_strongly_connected", counting)
    values = ChanceValues(_LOOP, ordering("x", "y"))
    values.at(WalkPrefix("s"))
    # t is reachable from s, so it was solved with it.
    assert values.at(replay(_LOOP, ["go"])) == Fraction(1, 3)
    values.at(WalkPrefix("s"))
    assert len(searches) == 1


def test_a_step_not_allowed_is_refused():
    with pytest.raises(
        VultronInvalidStateTransitionError, match="not allowed"
    ):
        find_step(_FORK, "s", "missing")
    with pytest.raises(
        VultronInvalidStateTransitionError, match="not allowed"
    ):
        ChanceValues(_FORK, ordering("a", "b")).change(WalkPrefix("A"), "a")


def test_a_step_named_twice_is_refused_as_ambiguous():
    model = _Graph("s", {"s": (("a", "t", _NONE), ("a", "u", _NONE))})
    with pytest.raises(VultronInvalidStateTransitionError, match="ambiguous"):
        replay(model, ["a"])


def test_a_prefix_records_each_steps_events_together():
    model = _Graph("s", {"s": (("a", "end", frozenset({"b"})),)})
    prefix = replay(model, ["a"])
    assert prefix == WalkPrefix("end", (frozenset({"a", "b"}),))
    assert ChanceValues(model, ordering("a", "b")).at(prefix) == 0


def test_a_step_given_whole_picks_one_of_an_ambiguous_event():
    model = _Graph("s", {"s": (("a", "t", _NONE), ("a", "u", _NONE))})
    to_u = Step("a", "u")
    assert take_step(model, "s", to_u) is to_u
    assert replay(model, [to_u]) == WalkPrefix("u", (frozenset({"a"}),))
    values = ChanceValues(model, ordering("a", "b"))
    assert values.change(WalkPrefix("s"), to_u) == 0


def test_a_step_given_whole_must_be_allowed():
    with pytest.raises(
        VultronInvalidStateTransitionError, match="not allowed"
    ):
        take_step(_FORK, "s", Step("a", "B"))


def test_a_reading_gives_the_scope_chance_and_the_expected_outcome() -> None:
    # Scoped to y.  From s: go to t or x (no y), each 1/2; from t: back to s
    # or y, each 1/2.  So P(y | s) = 1/2 · P(y | t) and P(y | t) =
    # 1/2 · P(y | s) + 1/2, giving 1/3 from s and 2/3 from t.  x never
    # precedes y on a walk that meets y, so the conditional value is 0, and
    # the expected outcome is 1 - entered: 2/3 from s, 1/3 from t.
    values = ChanceValues(_LOOP, ordering("x", "y", given=["y"]))
    start = values.reading(WalkPrefix("s"))
    assert start == ChanceReading(Fraction(0), Fraction(1, 3), Fraction(2, 3))
    mid = values.reading(replay(_LOOP, ["go"]))
    assert mid == ChanceReading(Fraction(0), Fraction(2, 3), Fraction(1, 3))
    assert values.at(WalkPrefix("s")) == start.value


def test_a_scope_the_walk_can_no_longer_enter_counts_as_met() -> None:
    values = ChanceValues(_LOOP, ordering("x", "y", given=["y"]))
    ended = values.reading(replay(_LOOP, ["x"]))
    assert ended == ChanceReading(None, Fraction(0), Fraction(1))
    unscoped = ChanceValues(_LOOP, ordering("x", "y"))
    assert unscoped.reading(WalkPrefix("s")).entered == 1


def test_an_expected_outcome_weighs_the_value_by_the_scope_chance() -> None:
    assert expected_outcome(Fraction(1, 4), Fraction(1, 2)) == Fraction(7, 8)
    assert expected_outcome(Fraction(0), None) == 1
    assert expected_outcome(Fraction(1), Fraction(0)) == 0


# ---------------------------------------------------------------------------
# The ends the walk can still reach
# ---------------------------------------------------------------------------


def _end_states():
    done = VendorPath(RM.CLOSED, CS_vf.VF, CS_d.D)
    active = JointState((done,), CS_pxa.pxa, EM.ACTIVE)
    ended = JointState(
        (done,), CS_pxa.PXA, EM.EXITED, EmbargoEnd.THREAT_SIGNAL
    )
    ex_own, p = Event(EventKind.EXIT_OWN_TERMS), Event(EventKind.P)
    return ONE_VENDOR_MODEL, active, ended, ex_own, p


def test_the_reachable_ends_are_found_from_a_prefix():
    model, active, ended, ex_own, p = _end_states()
    query = ordering(ex_own, p)
    met_sets = {
        met for _, met in reachable_ends(model, query, WalkPrefix(active))
    }
    assert met_sets == {frozenset(), frozenset({0})}
    assert {
        met for _, met in reachable_ends(model, query, WalkPrefix(ended))
    } == {frozenset()}


def test_a_reachable_end_outside_the_scope_is_listed_with_what_it_saw():
    """``given`` is not applied: the caller tells a scope never entered
    from an ordering broken."""
    model, _, ended, ex_own, p = _end_states()
    ends = reachable_ends(
        model, ordering(p, p, given=[ex_own]), WalkPrefix(ended)
    )
    assert ends
    assert all(ex_own not in seen for seen, _ in ends)


def test_reachable_ends_from_the_start_decide_implies():
    model, _, _, ex_own, p = _end_states()
    assert implies(model, ordering(ex_own, p), ordering(ex_own, p))
    assert not implies(model, ordering(p, ex_own), ordering(ex_own, p))
