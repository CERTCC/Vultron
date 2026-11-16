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

"""The indifference walk, solved exactly as an absorbing Markov chain (ADR-0182).

A :class:`ChanceModel` names a start state and, for each state, the steps
allowed next.  The walk takes each allowed step with equal probability (the
principle of indifference, ``random_walk.md``) and ends in a state with no
step.  A model may hold cycles — an embargo revision proposed and rejected, a
report deferred and accepted again — so a history can be arbitrarily long, and
no enumeration of histories is possible in general.

:func:`frequency` therefore never samples and never enumerates.  It augments
each state with what an :class:`OrderingQuery` needs to remember (which
watched events have occurred, and which orderings have been met), splits the
augmented graph into strongly connected components, and solves them sink
first: an acyclic component is one average of already-solved values, and a
cycle is a small linear system solved with :class:`fractions.Fraction`.  The
result is the exact chance frequency, not an estimate.

:class:`ChanceValues` keeps that solution for any point a walk can reach, not
only the start: given a :class:`WalkPrefix` (the state a walk is in and the
events of each step that brought it there), it gives the query's exact value
from there, and a step's expected change is the value after the step minus the
value before it.  The table fills on demand and keeps every value it solves,
so repeated lookups cost a dictionary read.

An ordering ``a ≺ b`` holds when ``a`` occurs at a step strictly before the
step at which ``b`` first occurs, or ``a`` occurs and ``b`` never does.  Two
events emitted by the same step (public awareness and the embargo exit it
forces) are simultaneous, so neither precedes the other.  An event counts at
its first occurrence; a later recurrence (a report accepted again after a
deferral) changes nothing.
"""

from collections.abc import Callable, Hashable, Iterable
from fractions import Fraction
from typing import NamedTuple, Protocol

from vultron.errors import VultronInvalidStateTransitionError


class Step[S: Hashable, E: Hashable](NamedTuple):
    """One allowed move: the event it is, the events it also emits, the state it reaches.

    ``also`` holds the events a coupling rule makes occur in the same step,
    such as the threat-signal embargo exit that public awareness forces.
    """

    event: E
    state: S
    also: frozenset[E] = frozenset()

    @property
    def events(self) -> frozenset[E]:
        """Every event this step emits."""
        return self.also | {self.event}


class ChanceModel[S: Hashable, E: Hashable](Protocol):
    """A state graph the indifference walk runs over."""

    @property
    def initial(self) -> S:
        """The state every walk starts in."""
        ...

    def steps(self, state: S) -> tuple[Step[S, E], ...]:
        """The steps allowed from *state*, each to a distinct state.

        An empty tuple marks *state* as one in which the walk ends.  The walk
        asks once per augmented state, so a model whose steps are costly to
        work out memoizes them, as :class:`.JointModel` does.
        """
        ...


def find_step[S: Hashable, E: Hashable](
    model: ChanceModel[S, E], state: S, event: E
) -> Step[S, E]:
    """The one step *event* allowed from *state*.

    Raises:
        VultronInvalidStateTransitionError: the model allows no step *event*
            from *state*, or more than one (as when accepting one of several
            pending embargo proposals can start the embargo as ``ACTIVE`` or
            as ``REVISE``).
    """
    matches = [s for s in model.steps(state) if s.event == event]
    if len(matches) != 1:
        reason = "is not allowed" if not matches else "is ambiguous"
        raise VultronInvalidStateTransitionError(
            f"{event} {reason} from {state}"
        )
    return matches[0]


class WalkPrefix[S: Hashable, E: Hashable](NamedTuple):
    """A walk partway: the state it is in, and what each step taken so far emitted.

    ``history`` holds, in order, the events of each step from the model's
    start to ``state``.  A desideratum's value depends on it as well as on the
    state, because an ordering already met or broken stays so: two walks in
    the same state can have different values.  Events one step emitted are
    one entry, because they are simultaneous.
    """

    state: S
    history: tuple[frozenset[E], ...] = ()

    def then(self, step: Step[S, E]) -> WalkPrefix[S, E]:
        """This prefix extended by *step*."""
        return WalkPrefix(step.state, (*self.history, step.events))


def replay[S: Hashable, E: Hashable](
    model: ChanceModel[S, E], events: Iterable[E]
) -> WalkPrefix[S, E]:
    """The prefix reached from the model's start by the steps *events* name, in order.

    Raises:
        VultronInvalidStateTransitionError: some event is not one allowed
            step from the state reached before it (:func:`find_step`).
    """
    prefix: WalkPrefix[S, E] = WalkPrefix(model.initial)
    for event in events:
        prefix = prefix.then(find_step(model, prefix.state, event))
    return prefix


class Ordering[E: Hashable](NamedTuple):
    """The ordering ``before ≺ after``."""

    before: E
    after: E


class OrderingQuery[E: Hashable](NamedTuple):
    """Every ordering in ``orderings`` holds, among walks where every ``given`` occurs.

    A desideratum is one ordering; a conjunction of desiderata (used to test
    whether one implies another) is several.  ``given`` scopes a desideratum
    to the cases it is measured over, such as vendors whose report reaches
    Valid.
    """

    orderings: tuple[Ordering[E], ...]
    given: frozenset[E] = frozenset()

    @property
    def watched(self) -> frozenset[E]:
        """The events whose first occurrence the walk must remember."""
        named = {e for o in self.orderings for e in o}
        return frozenset(named) | self.given


class WalkNeverEndsError(ValueError):
    """A set of states the walk can enter but never leave holds no end state.

    The walk's probability mass would circulate forever, so no frequency is
    defined; the model's rules are missing an exit.
    """


class _Node[S: Hashable, E: Hashable](NamedTuple):
    """A model state, with the watched events seen and the orderings met so far."""

    state: S
    seen: frozenset[E]
    met: frozenset[int]


def _advance[E: Hashable](
    query: OrderingQuery[E],
    seen: frozenset[E],
    met: frozenset[int],
    emitted: frozenset[E],
) -> tuple[frozenset[E], frozenset[int]]:
    """The remembered events and met orderings after a step emitting *emitted*."""
    watched_now = emitted & query.watched
    if not watched_now - seen:
        return seen, met
    newly_met = {
        index
        for index, (before, after) in enumerate(query.orderings)
        if before in watched_now
        and before not in seen
        and after not in seen
        and after not in emitted
    }
    return seen | watched_now, met | newly_met


def _strongly_connected[N: Hashable](
    start: N, successors: Callable[[N], list[N]]
) -> list[list[N]]:
    """Tarjan's components of the graph reachable from *start*, sinks first.

    Iterative, so a long chain of states cannot exhaust the recursion limit.
    """
    index: dict[N, int] = {}
    low: dict[N, int] = {}
    on_stack: set[N] = set()
    stack: list[N] = []
    components: list[list[N]] = []
    counter = 0
    work: list[tuple[N, int]] = [(start, 0)]
    children: dict[N, list[N]] = {}
    while work:
        node, child_index = work.pop()
        if child_index == 0:
            index[node] = low[node] = counter
            counter += 1
            stack.append(node)
            on_stack.add(node)
            children[node] = successors(node)
        kids = children[node]
        if child_index < len(kids):
            work.append((node, child_index + 1))
            child = kids[child_index]
            if child not in index:
                work.append((child, 0))
            elif child in on_stack:
                low[node] = min(low[node], index[child])
            continue
        if low[node] == index[node]:
            component: list[N] = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == node:
                    break
            components.append(component)
        if work:
            parent = work[-1][0]
            low[parent] = min(low[parent], low[node])
    return components


def _solve(
    matrix: list[list[Fraction]], rhs: list[list[Fraction]]
) -> list[list[Fraction]]:
    """Solve ``matrix · x = rhs`` exactly by Gauss–Jordan elimination.

    Raises:
        WalkNeverEndsError: the matrix is singular, which for ``I − P`` on a
            component means the walk cannot leave it.
    """
    size = len(matrix)
    rows = [matrix[i][:] + rhs[i][:] for i in range(size)]
    for col in range(size):
        pivot = next((r for r in range(col, size) if rows[r][col] != 0), None)
        if pivot is None:
            raise WalkNeverEndsError(
                "the walk can enter a set of states it never leaves"
            )
        rows[col], rows[pivot] = rows[pivot], rows[col]
        lead = rows[col][col]
        rows[col] = [value / lead for value in rows[col]]
        for r in range(size):
            factor = rows[r][col]
            if r != col and factor != 0:
                rows[r] = [
                    a - factor * b
                    for a, b in zip(rows[r], rows[col], strict=True)
                ]
    return [row[size:] for row in rows]


class _AugmentedWalk[S: Hashable, E: Hashable]:
    """The model's states, each paired with what *query* must remember of the walk so far."""

    def __init__(self, model: ChanceModel[S, E], query: OrderingQuery[E]):
        self._model = model
        self._query = query
        self._successors: dict[_Node[S, E], list[_Node[S, E]]] = {}
        self.start: _Node[S, E] = _Node(
            model.initial, frozenset(), frozenset()
        )

    def node(self, prefix: WalkPrefix[S, E]) -> _Node[S, E]:
        """The augmented node a walk is at after *prefix*."""
        seen: frozenset[E] = frozenset()
        met: frozenset[int] = frozenset()
        for emitted in prefix.history:
            seen, met = _advance(self._query, seen, met, emitted)
        return _Node(prefix.state, seen, met)

    def successors(self, node: _Node[S, E]) -> list[_Node[S, E]]:
        known = self._successors.get(node)
        if known is not None:
            return known
        found: list[_Node[S, E]] = []
        for step in self._model.steps(node.state):
            seen, met = _advance(self._query, node.seen, node.met, step.events)
            found.append(_Node(step.state, seen, met))
        self._successors[node] = found
        return found


class _Absorption[S: Hashable, E: Hashable]:
    """Expected terminal values of the walk from any node, each exact, solved on demand.

    *terminal_values* scores an ended walk from its remembered events and met
    orderings; a node's value is the probability-weighted sum over every way
    the walk can end from it.
    """

    def __init__(
        self,
        model: ChanceModel[S, E],
        query: OrderingQuery[E],
        terminal_values: Callable[
            [frozenset[E], frozenset[int]], tuple[int, ...]
        ],
    ):
        self.walk = _AugmentedWalk(model, query)
        self._terminal_values = terminal_values
        self._width = len(terminal_values(frozenset(), frozenset()))
        self._value: dict[_Node[S, E], tuple[Fraction, ...]] = {}

    def value(self, node: _Node[S, E]) -> tuple[Fraction, ...]:
        """The expected terminal values of the walk from *node*."""
        known = self._value.get(node)
        if known is None:
            self._solve_from(node)
            known = self._value[node]
        return known

    def _solve_from(self, start: _Node[S, E]) -> None:
        """Solve every node reachable from *start* that is not solved yet.

        A solved node is a sink to the component search: every node it
        reaches is solved too, so no unsolved node shares its component.
        """
        value = self._value
        successors = self.walk.successors

        def unsolved_successors(node: _Node[S, E]) -> list[_Node[S, E]]:
            return [] if node in value else successors(node)

        for component in _strongly_connected(start, unsolved_successors):
            first = component[0]
            if first in value:
                continue
            if len(component) > 1 or first in successors(first):
                self._solve_cycle(component)
            else:
                self._solve_acyclic(first)

    def _solve_acyclic(self, node: _Node[S, E]) -> None:
        """One average of already-solved values, or an ended walk's own score."""
        nexts = self.walk.successors(node)
        if not nexts:
            self._value[node] = tuple(
                Fraction(v) for v in self._terminal_values(node.seen, node.met)
            )
            return
        share = Fraction(1, len(nexts))
        self._value[node] = tuple(
            share * sum((self._value[n][k] for n in nexts), Fraction(0))
            for k in range(self._width)
        )

    def _solve_cycle(self, component: list[_Node[S, E]]) -> None:
        """A small linear system over the component, the rest already solved."""
        value, width = self._value, self._width
        order = {node: i for i, node in enumerate(component)}
        matrix = [[Fraction(0)] * len(component) for _ in component]
        rhs = [[Fraction(0)] * width for _ in component]
        for node, row in order.items():
            nexts = self.walk.successors(node)
            matrix[row][row] += 1
            share = Fraction(1, len(nexts))
            for n in nexts:
                if n in order:
                    matrix[row][order[n]] -= share
                else:
                    for k in range(width):
                        rhs[row][k] += share * value[n][k]
        for node, solved in zip(component, _solve(matrix, rhs), strict=True):
            value[node] = tuple(solved)


class ChanceValues[S: Hashable, E: Hashable]:
    """The exact value of one query under the indifference walk, from any point.

    The value from a :class:`WalkPrefix` is the chance, from there, that
    every ordering of the query holds, among the walks from there that meet
    every ``given`` event: the query's :func:`frequency` with the walk started
    where the prefix stands.  From the model's start it equals
    :func:`frequency`.

    Values are solved on first lookup and kept, so one instance serves many
    lookups over one model and query cheaply.
    """

    def __init__(self, model: ChanceModel[S, E], query: OrderingQuery[E]):
        self._model = model
        self._query = query
        every = frozenset(range(len(query.orderings)))

        def scores(seen: frozenset[E], met: frozenset[int]) -> tuple[int, int]:
            scoped = query.given <= seen
            return int(scoped and met == every), int(scoped)

        self._absorption = _Absorption(model, query, scores)

    @property
    def model(self) -> ChanceModel[S, E]:
        """The model the values are solved over."""
        return self._model

    @property
    def query(self) -> OrderingQuery[E]:
        """The query the values are of."""
        return self._query

    def at(self, prefix: WalkPrefix[S, E]) -> Fraction | None:
        """The query's value from *prefix*, or ``None`` when no walk from there meets ``given``.

        At a state with no allowed step, this is the walk's own outcome:
        ``1`` or ``0``, or ``None`` when ``given`` was not met.

        Raises:
            WalkNeverEndsError: the walk from *prefix* can circulate forever.
        """
        held, scoped = self._absorption.value(
            self._absorption.walk.node(prefix)
        )
        return None if scoped == 0 else held / scoped

    def change(self, prefix: WalkPrefix[S, E], event: E) -> Fraction | None:
        """The expected change of the step *event* from *prefix*.

        The value after the step minus the value before it; positive when the
        step makes the query likelier to hold than leaving the case to chance.
        ``None`` when either value is undefined.

        Raises:
            VultronInvalidStateTransitionError: *event* is not one allowed
                step from the prefix's state (:func:`find_step`).
        """
        after = self.at(
            prefix.then(find_step(self._model, prefix.state, event))
        )
        before = self.at(prefix)
        return difference(after, before)


def difference(
    after: Fraction | None, before: Fraction | None
) -> Fraction | None:
    """``after - before``, or ``None`` when either value is undefined."""
    if after is None or before is None:
        return None
    return after - before


def frequency[S: Hashable, E: Hashable](
    model: ChanceModel[S, E], query: OrderingQuery[E]
) -> Fraction:
    """The exact chance frequency of *query* under the indifference walk on *model*.

    The probability that every ordering holds, divided by the probability
    that every ``given`` event occurs.

    Raises:
        WalkNeverEndsError: the model lets the walk circulate forever.
        ValueError: no walk on *model* meets ``given``, so the frequency is
            undefined.
    """
    value = ChanceValues(model, query).at(WalkPrefix(model.initial))
    if value is None:
        raise ValueError(
            f"no walk on the model meets every given event of {query!r}"
        )
    return value


def ordering[E: Hashable](
    before: E, after: E, given: Iterable[E] = ()
) -> OrderingQuery[E]:
    """The query for the single ordering ``before ≺ after``."""
    return OrderingQuery((Ordering(before, after),), frozenset(given))


def implies[S: Hashable, E: Hashable](
    model: ChanceModel[S, E],
    stronger: OrderingQuery[E],
    weaker: OrderingQuery[E],
) -> bool:
    """Whether every walk on *model* that meets *stronger* also meets *weaker*.

    Both are judged among walks in which every ``given`` event of either
    occurs.  Every finite history of the walk has positive probability, so
    this is a search for one history that meets *stronger* and fails
    *weaker*; it needs no probabilities and holds exactly when the chance
    frequency of *stronger* and of the two together are equal.
    """
    joined = OrderingQuery(
        stronger.orderings + weaker.orderings, stronger.given | weaker.given
    )
    needed = frozenset(range(len(stronger.orderings)))
    every = frozenset(range(len(joined.orderings)))
    walk = _AugmentedWalk(model, joined)
    seen_nodes = {walk.start}
    pending = [walk.start]
    while pending:
        node = pending.pop()
        nexts = walk.successors(node)
        if not nexts and (
            joined.given <= node.seen
            and needed <= node.met
            and node.met != every
        ):
            return False
        for n in nexts:
            if n not in seen_nodes:
                seen_nodes.add(n)
                pending.append(n)
    return True
