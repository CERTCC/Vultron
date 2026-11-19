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
"""The generated action rules: move advice stated as rules (ADR-0216, SHD-05-007).

For each move and each band, :func:`generated_rules` groups the valid
positions of one vendor where move advice always gives the move that band
(:func:`~vultron.measure.action_rules.verdicts.vendor_points`) into patterns
in the authored rules' pattern language (SHD-05-015).  "Always" means for
every set of desiderata a history can leave open there.  Where the band
depends on which are open, :func:`conditional_verdicts` states each band
with the desiderata that give it, rather than picking one history (#6676,
D6; SHD-05-029).  A verdict on an event the position forces next is a rule
of its own, marked forced: the public learning of the vul beside a public
exploit is not a publication (#6676, D10).  A pattern may also
cover combinations of states no walk reaches, since no position stands
there, but never a valid position where the move gets another band or none.

The grouping is greedy and deterministic: each position not yet covered, in
walk order, seeds the pattern of its own states, which widens one CS letter,
then one RM state, then one EM state at a time, in their enum orders,
wherever it still covers no other position; a pattern the others cover is
then dropped.  A part that does not reach every state is cut to the states
of the positions the pattern covers.  The same advice always gives the same
rules.

A move move advice gives no band, such as a PEC move (#6677) or a chance
event, has no generated rule (SHD-05-017).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from functools import cache
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vultron.core.states.cs import CS
from vultron.core.states.em import EM, EM_TRIGGER_ROLES, EM_Trigger
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.measure.action_rules.model import (
    ANY_ROLE,
    Machine,
    MoveName,
    RulePattern,
    cs_pattern_matches,
    machine_of,
    move_advice_desiderata,
)
from vultron.measure.action_rules.verdicts import VendorPoint, vendor_points
from vultron.measure.advice.bands import BAND_ORDER, Band
from vultron.primitives import NonEmptyString


class GeneratedRule(BaseModel):
    """One move's band over the positions of one vendor, as patterns.

    Fields:
        move: The move, by name.
        role: The role move advice gives the move: the vendor for an RM or
            CS move, and for an EM move the role the EM trigger roles table
            gives its trigger, or any role (SHD-05-016).
        band: The band the move gets at every position the patterns match,
            whatever desiderata are still open.
        forced: Whether the move is the event those positions force next, so
            it comes whatever anyone does.
        patterns: The patterns, none with a PEC part.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    move: MoveName
    role: CVDRole | Literal["any"]
    band: Band
    forced: bool = False
    patterns: tuple[RulePattern, ...] = Field(min_length=1)


class ConditionalBranch(BaseModel):
    """One band of a conditional verdict, and the history that gives it.

    Fields:
        band: The band.
        open: The deciding desiderata still open on every history that
            gives this band, by plain name.
        settled: The deciding desiderata already met or broken on every
            history that gives this band.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    band: Band
    open: tuple[NonEmptyString, ...] = ()
    settled: tuple[NonEmptyString, ...] = ()

    @model_validator(mode="after")
    def _names_its_history(self) -> ConditionalBranch:
        if not (self.open or self.settled):
            raise ValueError(
                "a conditional branch names the desiderata that give it"
            )
        return self

    @property
    def caveat(self) -> str:
        """The branch as text: its band, and when it holds."""
        when = []
        if self.open:
            when.append(f"while {', '.join(self.open)} are still open")
        if self.settled:
            when.append(
                f"once {', '.join(self.settled)} are already met or broken"
            )
        return f"{self.band} {' and '.join(when)}"


class ConditionalVerdict(BaseModel):
    """A move whose band at one position depends on its history (#6676, D6;
    SHD-05-029).

    Fields:
        move: The move, by name.
        role: The role move advice gives the move (:func:`move_role`).
        position: The vendor's RM, CS and EM states.
        branches: Each band, with the desiderata that give it, in band
            order.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    move: MoveName
    role: CVDRole | Literal["any"]
    position: PositionKey
    branches: tuple[ConditionalBranch, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _distinct_bands(self) -> ConditionalVerdict:
        bands = [b.band for b in self.branches]
        if len(set(bands)) != len(bands):
            raise ValueError(
                "each branch of a conditional verdict has its band"
            )
        return self

    @property
    def caveat(self) -> str:
        """The verdict as text: each branch's band and when it holds."""
        return "; ".join(b.caveat for b in self.branches)


def move_role(move: str) -> CVDRole | Literal["any"]:
    """The role move advice gives *move* (SHD-05-016)."""
    if machine_of(move) is Machine.EM:
        return EM_TRIGGER_ROLES[EM_Trigger(move.split(".", 1)[1])] or ANY_ROLE
    return CVDRole.VENDOR


class PositionKey(NamedTuple):
    """One vendor's RM, CS and EM states: a position with no PEC part."""

    rm: RM
    cs: CS
    em: EM


class _Cube(NamedTuple):
    """A pattern while it grows: a set of states for each part, and the CS
    letters."""

    rm: frozenset[RM]
    letters: tuple[str, ...]
    em: frozenset[EM]

    def covers(self, key: PositionKey) -> bool:
        return (
            key.rm in self.rm
            and key.em in self.em
            and cs_pattern_matches("".join(self.letters), key.cs)
        )

    def pattern(self) -> RulePattern:
        return RulePattern(
            cs="".join(self.letters),
            rm=None if self.rm == frozenset(RM) else self.rm,
            em=None if self.em == frozenset(EM) else self.em,
        )


def _seed(key: PositionKey) -> _Cube:
    return _Cube(frozenset({key.rm}), tuple(key.cs.name), frozenset({key.em}))


def _widen(cube: _Cube, others: Sequence[PositionKey]) -> _Cube:
    """*cube* widened part by part while it covers none of *others*."""

    def clear(candidate: _Cube) -> bool:
        return not any(candidate.covers(k) for k in others)

    for index in range(len(cube.letters)):
        letters = list(cube.letters)
        letters[index] = "."
        candidate = cube._replace(letters=tuple(letters))
        if clear(candidate):
            cube = candidate
    for rm in RM:
        candidate = cube._replace(rm=cube.rm | {rm})
        if clear(candidate):
            cube = candidate
    for em in EM:
        candidate = cube._replace(em=cube.em | {em})
        if clear(candidate):
            cube = candidate
    return cube


def _trim(cube: _Cube, targets: Sequence[PositionKey]) -> _Cube:
    """*cube* with each RM and EM set that is not every state cut to the
    states of the positions it covers, so it names no state only a
    combination no walk reaches would use."""
    covered = [k for k in targets if cube.covers(k)]
    rm = (
        cube.rm
        if cube.rm == frozenset(RM)
        else frozenset(k.rm for k in covered)
    )
    em = (
        cube.em
        if cube.em == frozenset(EM)
        else frozenset(k.em for k in covered)
    )
    return cube._replace(rm=rm, em=em)


def group_positions(
    targets: Sequence[PositionKey], others: Sequence[PositionKey]
) -> tuple[RulePattern, ...]:
    """Patterns whose union holds every one of *targets* and none of
    *others*, greedily, in *targets*' order.

    Raises:
        ValueError: A position is both a target and one of *others*.
    """
    shared = set(targets) & set(others)
    if shared:
        raise ValueError(
            f"{len(shared)} positions are both targets and others; no"
            " pattern can hold one and not the other"
        )
    cubes: list[_Cube] = []
    uncovered = list(targets)
    while uncovered:
        cube = _trim(_widen(_seed(uncovered[0]), others), targets)
        cubes.append(cube)
        uncovered = [k for k in uncovered if not cube.covers(k)]
    kept = list(cubes)
    for cube in reversed(cubes):
        rest = [c for c in kept if c is not cube]
        if all(any(c.covers(k) for c in rest) for k in targets):
            kept = rest
    return tuple(c.pattern() for c in kept)


def _key(point: VendorPoint) -> PositionKey:
    p = point.position
    return PositionKey(p.rm, p.cs, p.em)


class _Variant(NamedTuple):
    band: Band
    forced: bool
    open: frozenset[str]


def _variants(
    points: Iterable[VendorPoint],
) -> dict[tuple[str, PositionKey], list[_Variant]]:
    """Each scored move at each position, once for each point there, in walk
    order."""
    found: dict[tuple[str, PositionKey], list[_Variant]] = {}
    for point in points:
        key = _key(point)
        opened = frozenset(point.open_desiderata or ())
        for verdict in point.verdicts:
            if verdict.score is None:
                continue
            found.setdefault((verdict.move.name, key), []).append(
                _Variant(verdict.score.band, verdict.forced, opened)
            )
    return found


def _conditional(
    move: str, position: PositionKey, variants: Sequence[_Variant]
) -> ConditionalVerdict:
    """The verdict *variants* give *move* at *position*, by band."""
    every_open = frozenset.intersection(*(v.open for v in variants))
    deciding = frozenset.union(*(v.open for v in variants)) - every_open
    order = list(move_advice_desiderata())
    branches = []
    for band in BAND_ORDER:
        mine = [v.open for v in variants if v.band is band]
        if not mine:
            continue
        always = frozenset.intersection(*mine) & deciding
        never = deciding - frozenset.union(*mine)
        branches.append(
            ConditionalBranch(
                band=band,
                open=tuple(d for d in order if d in always),
                settled=tuple(d for d in order if d in never),
            )
        )
    return ConditionalVerdict(
        move=move,
        role=move_role(move),
        position=position,
        branches=tuple(branches),
    )


def _split(
    points: Sequence[VendorPoint],
) -> tuple[
    dict[tuple[str, Band, bool], list[PositionKey]],
    list[ConditionalVerdict],
]:
    """The positions where each move always gets one band, and the
    conditional verdicts where it does not.

    Raises:
        ValueError: A move is forced at a position on one history and not
            on another, which no position can be.
    """
    groups: dict[tuple[str, Band, bool], list[PositionKey]] = {}
    conditional: list[ConditionalVerdict] = []
    for (move, position), variants in _variants(points).items():
        if len({v.forced for v in variants}) > 1:
            raise ValueError(
                f"{move} is forced at {position} on some histories"
            )
        if len({v.band for v in variants}) == 1:
            first = variants[0]
            groups.setdefault((move, first.band, first.forced), []).append(
                position
            )
        else:
            conditional.append(_conditional(move, position, variants))
    return groups, conditional


def rules_from(points: Sequence[VendorPoint]) -> tuple[GeneratedRule, ...]:
    """The generated rules over *points*: one for each move, band and
    forced mark.

    In the order the moves are first scored in the walk, then in band order,
    the unforced rule first.
    """
    every = list(dict.fromkeys(_key(p) for p in points))
    groups, _ = _split(points)
    moves = list(dict.fromkeys(move for move, _, _ in groups))
    rules = []
    for move in moves:
        for band in BAND_ORDER:
            for forced in (False, True):
                targets = groups.get((move, band, forced))
                if not targets:
                    continue
                held = set(targets)
                others = [k for k in every if k not in held]
                rules.append(
                    GeneratedRule(
                        move=move,
                        role=move_role(move),
                        band=band,
                        forced=forced,
                        patterns=group_positions(targets, others),
                    )
                )
    return tuple(rules)


def conditionals_from(
    points: Sequence[VendorPoint],
) -> tuple[ConditionalVerdict, ...]:
    """The conditional verdicts over *points*, in walk order."""
    return tuple(_split(points)[1])


@cache
def generated_rules() -> tuple[GeneratedRule, ...]:
    """The generated action rules over every valid position of one vendor."""
    return rules_from(vendor_points())


@cache
def conditional_verdicts() -> tuple[ConditionalVerdict, ...]:
    """The conditional verdicts over every valid position of one vendor."""
    return conditionals_from(vendor_points())
