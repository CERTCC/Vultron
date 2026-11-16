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

"""The pathology cases of the move-band spike, P1 to P8 (#6450, ADR-0200).

Each pathology is a check that any advice method must pass on every
:class:`~test.measure.advice.cases.Case`.  A method is anything that gives an
:class:`Advice` for a case: the bands of ADR-0200, or a scalar aggregate of
the vendors' scores.  A check returns its failures, one line each, and an
empty list when the method passes the case.

The facts a check states about the case itself, such as which move
dominates which, come from :class:`Truth`: the outcome shifts against the
chance value (:func:`vultron.measure.advice.outcome_shift`) and the
definitions of ADR-0200, read through :func:`~vultron.measure.advice.band`
and :func:`~vultron.measure.advice.dominates`.  Those are the bands'
own functions, so for the bands P4 and P8 check the marks and layers
against the definitions, not the definitions themselves;
``test_bands.py`` tests the definitions on their own, P4 over every small
shift.

For a method with no bands, P2 asks only that it does not put publication
strictly first among the coordinator's moves, and P4 that it neither marks
the dominating move unhelpful nor shows it below the move it dominates.
"""

from collections.abc import Callable
from functools import cache
from typing import NamedTuple, Protocol

from test.measure.advice.cases import CASES, NO_HARM_FREE, Case
from vultron.measure.advice import (
    Band,
    ScopeParts,
    band,
    dominates,
    outcome_shift,
)
from vultron.measure.baselines import Event, EventKind, JointState, Step

type Move = Step[JointState, Event]

_K = EventKind


class Advice(Protocol):
    """What one method shows the analyst about one case's open moves."""

    def band(self, move: Move) -> Band | None:
        """The move's band, or ``None`` for a method with no bands."""
        ...

    def unhelpful(self, move: Move) -> bool:
        """Whether the method says the move does no better than chance."""
        ...

    def top(self, move: Move) -> bool:
        """Whether the method marks the move as a top move."""
        ...

    def leading_among_yours(self, move: Move) -> bool:
        """Whether the method marks the coordinator's move as leading."""
        ...

    def above(self, x: Move, y: Move) -> bool:
        """Whether the method shows *x* strictly before *y*."""
        ...

    def harms_shown(self, move: Move) -> frozenset[int]:
        """The vendors for which the method shows the move's negative shift."""
        ...


type Method = Callable[[Case], Advice]


class Truth:
    """The case's outcome shifts, and the ADR-0200 facts about them."""

    def __init__(self, case: Case):
        self.case = case
        self._shifts = {m: outcome_shift(case.prefix, m) for m in case.moves}

    def shift(self, move: Move) -> tuple[ScopeParts, ...]:
        return self._shifts[move]

    def band(self, move: Move) -> Band:
        return band(self._shifts[move])

    def dominates(self, x: Move, y: Move) -> bool:
        return dominates(self._shifts[x], self._shifts[y])

    def harmed(self, move: Move) -> frozenset[int]:
        """The vendors with a negative end or embargo part."""
        return frozenset(
            vendor
            for vendor, parts in enumerate(self._shifts[move], start=1)
            if parts.end < 0 or parts.embargo < 0
        )

    def touched(self, move: Move) -> frozenset[int]:
        """The vendors with a non-zero end or embargo part."""
        return frozenset(
            vendor
            for vendor, parts in enumerate(self._shifts[move], start=1)
            if parts.end != 0 or parts.embargo != 0
        )

    def raises_an_end(self, move: Move) -> bool:
        return any(p.end > 0 for p in self._shifts[move])

    def lowers_an_end(self, move: Move) -> bool:
        return any(p.end < 0 for p in self._shifts[move])

    def embargo_only(self, move: Move) -> bool:
        parts = self._shifts[move]
        return all(p.end == 0 for p in parts) and any(
            p.embargo != 0 for p in parts
        )


@cache
def truth(case: Case) -> Truth:
    return Truth(case)


type Check = Callable[[Case, Advice, Truth], list[str]]


def p1_notify_is_never_unhelpful(
    case: Case, advice: Advice, facts: Truth
) -> list[str]:
    """P1: a move that notifies a vendor is never unhelpful, and raises that vendor."""
    failures = []
    for move in case.moves:
        if move.event.kind is not _K.V:
            continue
        vendor = move.event.vendor
        assert vendor is not None
        if facts.shift(move)[vendor - 1].end <= 0:
            failures.append(
                f"{move.event}: vendor {vendor}'s end part is not positive"
            )
        if advice.unhelpful(move):
            failures.append(f"{move.event} is shown as unhelpful")
    return failures


def _coordinator_moves(case: Case) -> list[Move]:
    return [m for m in case.moves if case.yours(m)]


def p2_publication_is_not_preferred_to_an_extension(
    case: Case, advice: Advice, facts: Truth
) -> list[str]:
    """P2: publication now does not come before an embargo extension.

    When no coordinator move raises an end part, the extension is harm-free
    and publication now is unhelpful.  When publication now raises a ready
    vendor's end part, it is a trade-off move, below every harm-free move.
    """
    if not (case.has(_K.P) and case.has(_K.REVISION_PROPOSED)):
        return []
    publish = case.move(_K.P)
    extend = case.move(_K.REVISION_PROPOSED)
    yours = _coordinator_moves(case)
    no_raise = not any(facts.raises_an_end(m) for m in yours)
    if not no_raise and not facts.raises_an_end(publish):
        return []
    if advice.band(publish) is None:
        others = [m for m in yours if m != publish]
        if others and all(advice.above(publish, m) for m in others):
            return ["publication now is shown strictly first"]
        return []
    failures = []
    if no_raise:
        if advice.band(extend) is not Band.HARM_FREE:
            failures.append(
                f"the extension is {advice.band(extend)}, not harm-free"
            )
        if advice.band(publish) is not Band.UNHELPFUL:
            failures.append(
                f"publication now is {advice.band(publish)}, not unhelpful"
            )
        return failures
    if advice.band(publish) is not Band.TRADE_OFF:
        failures.append(
            f"publication now is {advice.band(publish)}, not a trade-off"
        )
    failures += [
        f"publication now is not below the harm-free {m.event}"
        for m in case.moves
        if advice.band(m) is Band.HARM_FREE and not advice.above(m, publish)
    ]
    return failures


def p3_each_harm_is_shown_with_its_vendor(
    case: Case, advice: Advice, facts: Truth
) -> list[str]:
    """P3: each negative outcome shift shows on its move, with its vendor."""
    return [
        f"{move.event}: vendor {vendor}'s negative shift is not shown"
        for move in case.moves
        for vendor in sorted(facts.harmed(move) - advice.harms_shown(move))
    ]


def p4_dominating_a_harm_free_move_is_harm_free(
    case: Case, advice: Advice, facts: Truth
) -> list[str]:
    """P4: a move that dominates a harm-free move is harm-free."""
    failures = []
    for x in case.moves:
        for y in case.moves:
            if not (facts.dominates(x, y) and facts.band(y) is Band.HARM_FREE):
                continue
            if advice.band(x) is None:
                if advice.unhelpful(x) or advice.above(y, x):
                    failures.append(
                        f"{x.event} dominates the harm-free {y.event} and is"
                        " shown as unhelpful or below it"
                    )
            elif advice.band(x) is not Band.HARM_FREE:
                failures.append(
                    f"{x.event} dominates the harm-free {y.event} and is"
                    f" {advice.band(x)}"
                )
    return failures


def p5_an_early_end_harms_each_vendor_it_touches(
    case: Case, advice: Advice, facts: Truth
) -> list[str]:
    """P5: ending an embargo early shows a negative shift for each vendor it touches."""
    failures = []
    for move in case.moves:
        if move.event.kind is not _K.EXIT_OTHER:
            continue
        for vendor in sorted(facts.touched(move)):
            if vendor not in facts.harmed(move):
                failures.append(f"vendor {vendor} has no negative part")
            if vendor not in advice.harms_shown(move):
                failures.append(
                    f"vendor {vendor}'s negative shift is not shown"
                )
    return failures


def p6_unhelpful_moves_get_no_mark(
    case: Case, advice: Advice, facts: Truth
) -> list[str]:
    """P6: an unhelpful move gets no top mark and no "leading among yours" mark.

    The harm-free band can be empty: :data:`NO_HARM_FREE` is a case in which
    it is, and a method with bands puts no move there.
    """
    failures = [
        f"the unhelpful {m.event} is marked {mark}"
        for m in case.moves
        if advice.unhelpful(m)
        for mark, marked in (
            ("top", advice.top(m)),
            ("leading among yours", advice.leading_among_yours(m)),
        )
        if marked
    ]
    if case == NO_HARM_FREE:
        failures += [
            f"{m.event} is harm-free"
            for m in case.moves
            if advice.band(m) is Band.HARM_FREE
        ]
    return failures


def p7_an_end_gain_dominates_an_embargo_only_move(
    case: Case, advice: Advice, facts: Truth
) -> list[str]:
    """P7: a move that raises an end part and lowers none is above every embargo-only move."""
    return [
        f"{x.event} is not shown above the embargo-only {y.event}"
        for x in case.moves
        if facts.raises_an_end(x) and not facts.lowers_an_end(x)
        for y in case.moves
        if facts.embargo_only(y) and not advice.above(x, y)
    ]


def p8_a_dominated_trade_off_is_not_top(
    case: Case, advice: Advice, facts: Truth
) -> list[str]:
    """P8: a trade-off move that a harm-free move dominates is not top."""
    return [
        f"the trade-off {y.event} is top, though {x.event} dominates it"
        for y in case.moves
        if facts.band(y) is Band.TRADE_OFF and advice.top(y)
        for x in case.moves
        if facts.band(x) is Band.HARM_FREE and facts.dominates(x, y)
    ]


type Witness = Callable[[Case, Truth], bool]


class Pathology(NamedTuple):
    """A check, and a test of whether a case gives the check anything to test."""

    name: str
    check: Check
    witness: Witness


def _any_move(kind: EventKind) -> Witness:
    return lambda case, facts: any(m.event.kind is kind for m in case.moves)


def _p2_witness(case: Case, facts: Truth) -> bool:
    return case.has(_K.P) and case.has(_K.REVISION_PROPOSED)


def _p4_witness(case: Case, facts: Truth) -> bool:
    return any(
        facts.dominates(x, y) and facts.band(y) is Band.HARM_FREE
        for x in case.moves
        for y in case.moves
    )


def _p7_witness(case: Case, facts: Truth) -> bool:
    return any(
        facts.raises_an_end(x) and not facts.lowers_an_end(x)
        for x in case.moves
    ) and any(facts.embargo_only(y) for y in case.moves)


def _p8_witness(case: Case, facts: Truth) -> bool:
    return any(
        facts.band(y) is Band.TRADE_OFF
        and facts.band(x) is Band.HARM_FREE
        and facts.dominates(x, y)
        for x in case.moves
        for y in case.moves
    )


PATHOLOGIES: tuple[Pathology, ...] = (
    Pathology("P1", p1_notify_is_never_unhelpful, _any_move(_K.V)),
    Pathology(
        "P2", p2_publication_is_not_preferred_to_an_extension, _p2_witness
    ),
    Pathology(
        "P3",
        p3_each_harm_is_shown_with_its_vendor,
        lambda case, facts: any(facts.harmed(m) for m in case.moves),
    ),
    Pathology("P4", p4_dominating_a_harm_free_move_is_harm_free, _p4_witness),
    Pathology(
        "P5",
        p5_an_early_end_harms_each_vendor_it_touches,
        lambda case, facts: any(
            m.event.kind is _K.EXIT_OTHER and facts.touched(m)
            for m in case.moves
        ),
    ),
    Pathology(
        "P6",
        p6_unhelpful_moves_get_no_mark,
        lambda case, facts: any(
            facts.band(m) is Band.UNHELPFUL for m in case.moves
        ),
    ),
    Pathology(
        "P7", p7_an_end_gain_dominates_an_embargo_only_move, _p7_witness
    ),
    Pathology("P8", p8_a_dominated_trade_off_is_not_top, _p8_witness),
)

ALL_CASES: tuple[Case, ...] = (*CASES, NO_HARM_FREE)
"""Every case a pathology runs over."""
