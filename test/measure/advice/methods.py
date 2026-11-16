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

"""The advice methods the spike compares (#6450).

* ``bands``: the bands, layers and marks of ADR-0200
  (:func:`vultron.measure.advice.advise`).
* Five scalar aggregates, the rejected option of ADR-0200: each move gets one
  case score, the aggregate of the notified vendors' scores after the move,
  as a case score summarizes the vendors that have a case-state sequence
  (CEH-05-001).  A vendor's score is its chance value, end and embargo
  parts added.  The aggregate puts the moves in order by that score; a move
  is unhelpful when its score is not above the case's score before it, and
  the top moves are those with the highest score.  One number shows no
  vendor's harm.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from math import prod
from statistics import median

from test.measure.advice.cases import Case
from test.measure.advice.pathologies import Advice, Method, Move
from vultron.core.states.rm import RM
from vultron.measure.advice import (
    BAND_ORDER,
    Band,
    MoveAdvice,
    advise,
    chance_values,
    dominates,
    move_shifts,
)
from vultron.measure.baselines.values import CasePrefix


@dataclass(frozen=True)
class BandAdvice:
    """ADR-0200's advice for one case."""

    advice: dict[Move, MoveAdvice[Move]]

    def band(self, move: Move) -> Band | None:
        return self.advice[move].band

    def unhelpful(self, move: Move) -> bool:
        return self.advice[move].band is Band.UNHELPFUL

    def top(self, move: Move) -> bool:
        return self.advice[move].top

    def leading_among_yours(self, move: Move) -> bool:
        return self.advice[move].leading_among_yours

    def above(self, x: Move, y: Move) -> bool:
        """A higher band, or the same band and *x* dominates *y* (its shade)."""
        bx, by = self.advice[x].band, self.advice[y].band
        if bx is not by:
            return BAND_ORDER.index(bx) < BAND_ORDER.index(by)
        return dominates(self.advice[x].shift, self.advice[y].shift)

    def harms_shown(self, move: Move) -> frozenset[int]:
        return frozenset(h.vendor for h in self.advice[move].harms)


@cache
def bands(case: Case) -> Advice:
    shifts = move_shifts(case.prefix, case.moves)
    return BandAdvice(advise(shifts, case.yours))


type Aggregate = Callable[[Sequence[Fraction]], tuple[Fraction, ...]]
"""The case score of the notified vendors' scores, compared as a tuple."""


def _median(scores: Sequence[Fraction]) -> tuple[Fraction, ...]:
    return (Fraction(median(scores)),)


def _mean(scores: Sequence[Fraction]) -> tuple[Fraction, ...]:
    return (sum(scores, Fraction(0)) / len(scores),)


def _maximin(scores: Sequence[Fraction]) -> tuple[Fraction, ...]:
    return (min(scores),)


def _mean_then_spread(scores: Sequence[Fraction]) -> tuple[Fraction, ...]:
    """The mean, then the smaller spread (highest score less lowest) first."""
    return (*_mean(scores), min(scores) - max(scores))


def _nash(scores: Sequence[Fraction]) -> tuple[Fraction, ...]:
    return (prod(scores, start=Fraction(1)),)


AGGREGATES: dict[str, Aggregate] = {
    "median": _median,
    "mean": _mean,
    "maximin": _maximin,
    "mean then spread": _mean_then_spread,
    "Nash product": _nash,
}


def notified_scores(prefix: CasePrefix) -> tuple[Fraction, ...]:
    """The score of each vendor that has received the report."""
    return tuple(
        parts.end + parts.embargo
        for path, parts in zip(
            prefix.state.vendors, chance_values(prefix), strict=True
        )
        if path.rm is not RM.START
    )


@dataclass(frozen=True)
class ScoreAdvice:
    """One case score for each move, from one aggregate."""

    before: tuple[Fraction, ...]
    score: dict[Move, tuple[Fraction, ...]]
    yours: frozenset[Move]

    def band(self, move: Move) -> Band | None:
        return None

    def unhelpful(self, move: Move) -> bool:
        return self.score[move] <= self.before

    def top(self, move: Move) -> bool:
        return self.score[move] == max(self.score.values())

    def leading_among_yours(self, move: Move) -> bool:
        return move in self.yours and self.score[move] == max(
            self.score[m] for m in self.yours
        )

    def above(self, x: Move, y: Move) -> bool:
        return self.score[x] > self.score[y]

    def harms_shown(self, move: Move) -> frozenset[int]:
        return frozenset()


def _scored(name: str) -> Method:
    aggregate = AGGREGATES[name]

    @cache
    def method(case: Case) -> Advice:
        prefix = case.prefix
        return ScoreAdvice(
            aggregate(notified_scores(prefix)),
            {
                m: aggregate(notified_scores(prefix.then(m)))
                for m in case.moves
            },
            frozenset(m for m in case.moves if case.yours(m)),
        )

    return method


METHODS: dict[str, Method] = {
    "bands": bands,
    **{name: _scored(name) for name in AGGREGATES},
}
