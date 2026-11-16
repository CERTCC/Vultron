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

"""The walk from where a case stands, and the ends it can still reach (ADR-0182).

A case that has already happened in part is scored through its completions:
the walk goes on from the state the case is in, not from the model's start
(ADR-0182).  :class:`StartedAt` is a model whose walk starts at a given
state, so :func:`~vultron.measure.baselines.walk.frequency` over it is the
chance that a query holds from there.  :func:`reachable_ends` answers the
other half of that scoring, the best and the worst a case can still reach:
the sets of orderings met at every end the walk can reach from the start,
found by search, with no probabilities.

Both read the walk of :mod:`~vultron.measure.baselines.walk`, so an ordering
here means what it means for a baseline.
"""

from collections.abc import Hashable

# The walk's own augmentation (what a query remembers of a walk so far), so a
# reachable end means here what it means for ``frequency`` and ``implies``.
from vultron.measure.baselines.walk import (
    ChanceModel,
    OrderingQuery,
    Step,
    _AugmentedWalk,
)


class StartedAt[S: Hashable, E: Hashable]:
    """*model*, with its walk started at *state* instead of its own start.

    Every step is *model*'s; only the start differs, so the walk from *state*
    is the walk *model* takes once it reaches *state*.  Two instances over the
    same model and state are equal, so a cache keyed on one finds the other.
    """

    def __init__(self, model: ChanceModel[S, E], state: S) -> None:
        self._model = model
        self._state = state

    @property
    def initial(self) -> S:
        """The state the walk starts in."""
        return self._state

    def steps(self, state: S) -> tuple[Step[S, E], ...]:
        """*model*'s steps from *state*."""
        return self._model.steps(state)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, StartedAt)
            and other._model is self._model
            and other._state == self._state
        )

    def __hash__(self) -> int:
        return hash((id(self._model), self._state))


def reachable_ends[S: Hashable, E: Hashable](
    model: ChanceModel[S, E], query: OrderingQuery[E]
) -> frozenset[frozenset[int]]:
    """The orderings of *query* met at each end the walk on *model* can reach.

    Each member is the set of indices into ``query.orderings`` met at one or
    more reachable ends, among the ends at which every ``given`` event
    occurred.  Every finite history of the walk has positive probability, so
    an outcome is reachable exactly when some history has it; the search
    needs no probabilities, as :func:`~vultron.measure.baselines.walk.implies`
    does not.
    """
    walk = _AugmentedWalk(model, query)
    seen = {walk.start}
    pending = [walk.start]
    ends: set[frozenset[int]] = set()
    while pending:
        node = pending.pop()
        nexts = walk.successors(node)
        if not nexts and query.given <= node.seen:
            ends.add(node.met)
        for successor in nexts:
            if successor not in seen:
                seen.add(successor)
                pending.append(successor)
    return frozenset(ends)
