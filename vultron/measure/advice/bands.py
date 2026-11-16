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

"""Bands, dominance, layers and marks over the open moves (ADR-0200 rules 4 to 8).

Every function here reads only the outcome shifts
(:mod:`vultron.measure.advice.shifts`), so it works on any move type: a
:class:`~vultron.measure.baselines.Step` of the joint model, or a synthetic
label in a test.
"""

from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from fractions import Fraction
from typing import NamedTuple

from vultron.measure.advice.shifts import ScopeShift


class Band(StrEnum):
    """The band an open move falls in, set only by its own outcome shifts."""

    HARM_FREE = "harm-free"
    TRADE_OFF = "trade-off"
    UNHELPFUL = "unhelpful"


BAND_ORDER: tuple[Band, ...] = (Band.HARM_FREE, Band.TRADE_OFF, Band.UNHELPFUL)
"""The order in which the page shows the bands, harm-free first."""


class Part(StrEnum):
    """The two parts of a vendor's scope."""

    END = "end"
    EMBARGO = "embargo"


def _ends(shift: ScopeShift) -> tuple[Fraction, ...]:
    return tuple(p.end for p in shift)


def _embargoes(shift: ScopeShift) -> tuple[Fraction, ...]:
    return tuple(p.embargo for p in shift)


def deciding_parts(shift: ScopeShift) -> tuple[Part, tuple[Fraction, ...]]:
    """The parts that decide a move's band: the end parts, or the embargo
    parts when every end part is zero."""
    ends = _ends(shift)
    if any(ends):
        return Part.END, ends
    return Part.EMBARGO, _embargoes(shift)


def band(shift: ScopeShift, threshold: Fraction = Fraction(0)) -> Band:
    """The band of a move with outcome shift *shift* (ADR-0200 rule 5).

    The sign test is strict: any non-zero deciding part counts.  A
    *threshold* above zero counts a part as zero when its size is at most
    the threshold; it exists only to measure how much a band rests on very
    small parts (#6450), and the advice itself uses none.

    Raises:
        ValueError: *threshold* is negative.
    """
    if threshold < 0:
        raise ValueError(f"a threshold cannot be negative, not {threshold}")
    ends = [e if abs(e) > threshold else Fraction(0) for e in _ends(shift)]
    parts = ends
    if not any(ends):
        parts = [
            m if abs(m) > threshold else Fraction(0) for m in _embargoes(shift)
        ]
    if not any(p > 0 for p in parts):
        return Band.UNHELPFUL
    if any(p < 0 for p in parts):
        return Band.TRADE_OFF
    return Band.HARM_FREE


def _pareto(x: Sequence[Fraction], y: Sequence[Fraction]) -> bool:
    """*x* at least *y* everywhere and above it somewhere."""
    pairs = list(zip(x, y, strict=True))
    return all(a >= b for a, b in pairs) and any(a > b for a, b in pairs)


def dominates(x: ScopeShift, y: ScopeShift) -> bool:
    """Whether a move with shift *x* dominates one with shift *y* (ADR-0200 rule 4).

    The end parts decide; when every end part is equal, the embargo parts
    do.  Two moves that trade off against each other do not dominate each
    other.

    Raises:
        ValueError: *x* and *y* hold different numbers of vendors.
    """
    if len(x) != len(y):
        raise ValueError(
            f"shifts of {len(x)} and {len(y)} vendors do not compare"
        )
    if _ends(x) != _ends(y):
        return _pareto(_ends(x), _ends(y))
    return _pareto(_embargoes(x), _embargoes(y))


def layers[M](shifts: Mapping[M, ScopeShift]) -> dict[M, int]:
    """Each move's depth in the dominance order (ADR-0200 rule 6).

    Layer 1 holds the moves no move of *shifts* dominates; layer 2 those
    that only layer-1 moves dominate; and so on.
    """
    remaining = dict(shifts)
    found: dict[M, int] = {}
    depth = 0
    while remaining:
        depth += 1
        layer = [
            m
            for m, s in remaining.items()
            if not any(dominates(t, s) for n, t in remaining.items() if n != m)
        ]
        for move in layer:
            found[move] = depth
            del remaining[move]
    return found


class Harm(NamedTuple):
    """One negative part of a move's shift, with its vendor and size."""

    vendor: int
    part: Part
    size: Fraction


def harms(shift: ScopeShift) -> tuple[Harm, ...]:
    """Every negative end and embargo part of *shift*, by vendor (ADR-0200 rule 8).

    A negative part means worse than the chance value, not a broken
    desideratum.
    """
    found = []
    for vendor, parts in enumerate(shift, start=1):
        if parts.end < 0:
            found.append(Harm(vendor, Part.END, parts.end))
        if parts.embargo < 0:
            found.append(Harm(vendor, Part.EMBARGO, parts.embargo))
    return tuple(found)


class MoveAdvice[M](NamedTuple):
    """What the page shows for one open move."""

    move: M
    shift: ScopeShift
    band: Band
    layer: int
    top: bool
    """A harm-free or trade-off move in layer 1."""
    leading_among_yours: bool
    """The coordinator's harm-free or trade-off move that none of the
    coordinator's other open moves dominates."""
    harms: tuple[Harm, ...]


def advise[M](
    shifts: Mapping[M, ScopeShift], yours: Callable[[M], bool]
) -> dict[M, MoveAdvice[M]]:
    """Each open move's band, layer, marks and harms (ADR-0200 rules 5 to 8).

    *shifts* holds every open move of the case and its outcome shift;
    *yours* tells which of them the coordinator makes.
    """
    depth = layers(shifts)
    mine = {m: s for m, s in shifts.items() if yours(m)}
    found: dict[M, MoveAdvice[M]] = {}
    for move, shift in shifts.items():
        moved = band(shift)
        helps = moved is not Band.UNHELPFUL
        leading = (
            helps
            and move in mine
            and not any(
                dominates(other, shift)
                for n, other in mine.items()
                if n != move
            )
        )
        found[move] = MoveAdvice(
            move,
            shift,
            moved,
            depth[move],
            helps and depth[move] == 1,
            leading,
            harms(shift),
        )
    return found
