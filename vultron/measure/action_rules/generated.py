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
"""The generated action rules: move advice stated as rules (ADR-0216 rule 5).

For each move and each band, :func:`generated_rules` groups the valid
positions of one vendor where move advice gives the move that band
(:func:`~vultron.measure.action_rules.verdicts.vendor_points`) into patterns
in the authored rules' pattern language (SHD-05-015).  A pattern may also
cover combinations of states no walk reaches, since no position stands
there, but never a valid position where the move gets another band or none.

The grouping is greedy and deterministic: each position not yet covered, in
walk order, seeds the pattern of its own states, which widens one CS letter,
then one RM state, then one EM state at a time, in their enum orders,
wherever it still covers no other position; a pattern the others cover is
then dropped.  A part that does not reach every state is cut to the states
of the positions the pattern covers.  The same advice always gives the same rules.

A move move advice gives no band, such as a PEC move (#6677) or a chance
event, has no generated rule (SHD-05-017).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from functools import cache
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from vultron.core.states.cs import CS
from vultron.core.states.cs_invariants import CS_EVENTS, cs_happened_events
from vultron.core.states.em import EM, EM_TRIGGER_ROLES, EM_Trigger
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.measure.action_rules.model import (
    ANY_ROLE,
    Machine,
    MoveName,
    RulePattern,
    machine_of,
)
from vultron.measure.action_rules.verdicts import VendorPoint, vendor_points
from vultron.measure.advice.bands import BAND_ORDER, Band


class GeneratedRule(BaseModel):
    """One move's band over the positions of one vendor, as patterns.

    Fields:
        move: The move, by name.
        role: The role move advice gives the move: the vendor for an RM or
            CS move, and for an EM move the role the EM trigger roles table
            gives its trigger, or any role (SHD-05-016).
        band: The band the move gets at every position the patterns match.
        patterns: The patterns, none with a PEC part.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    move: MoveName
    role: CVDRole | Literal["any"]
    band: Band
    patterns: tuple[RulePattern, ...] = Field(min_length=1)


def move_role(move: str) -> CVDRole | Literal["any"]:
    """The role move advice gives *move* (SHD-05-016)."""
    if machine_of(move) is Machine.EM:
        return EM_TRIGGER_ROLES[EM_Trigger(move.split(".", 1)[1])] or ANY_ROLE
    return CVDRole.VENDOR


class _Key(NamedTuple):
    rm: RM
    cs: CS
    em: EM


class _Cube(NamedTuple):
    """A pattern while it grows: a set of states for each part, and the CS
    letters."""

    rm: frozenset[RM]
    letters: tuple[str, ...]
    em: frozenset[EM]

    def covers(self, key: _Key) -> bool:
        happened = cs_happened_events(key.cs)
        return (
            key.rm in self.rm
            and key.em in self.em
            and all(
                letter == "." or (letter.isupper() == (event in happened))
                for event, letter in zip(CS_EVENTS, self.letters, strict=True)
            )
        )

    def pattern(self) -> RulePattern:
        return RulePattern(
            cs="".join(self.letters),
            rm=None if self.rm == frozenset(RM) else self.rm,
            em=None if self.em == frozenset(EM) else self.em,
        )


def _seed(key: _Key) -> _Cube:
    return _Cube(frozenset({key.rm}), tuple(key.cs.name), frozenset({key.em}))


def _widen(cube: _Cube, others: Sequence[_Key]) -> _Cube:
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


def _trim(cube: _Cube, targets: Sequence[_Key]) -> _Cube:
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
    targets: Sequence[_Key], others: Sequence[_Key]
) -> tuple[RulePattern, ...]:
    """Patterns whose union holds every one of *targets* and none of
    *others*, greedily, in *targets*' order."""
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


def _key(point: VendorPoint) -> _Key:
    p = point.position
    return _Key(p.rm, p.cs, p.em)


def _bands(
    points: Iterable[VendorPoint],
) -> dict[tuple[str, Band], list[_Key]]:
    """The positions where each move gets each band, in walk order."""
    found: dict[tuple[str, Band], list[_Key]] = {}
    for point in points:
        key = _key(point)
        for verdict in point.verdicts:
            if verdict.score is None:
                continue
            entry = found.setdefault(
                (verdict.move.name, verdict.score.band), []
            )
            if key not in entry:
                entry.append(key)
    return found


def rules_from(points: Sequence[VendorPoint]) -> tuple[GeneratedRule, ...]:
    """The generated rules over *points*: one for each move and band.

    In the order the moves are first scored in the walk, then in band order.
    """
    every = [_key(p) for p in points]
    bands = _bands(points)
    moves = list(dict.fromkeys(move for move, _ in bands))
    rules = []
    for move in moves:
        for band in BAND_ORDER:
            targets = bands.get((move, band))
            if not targets:
                continue
            held = set(targets)
            others = [k for k in every if k not in held]
            rules.append(
                GeneratedRule(
                    move=move,
                    role=move_role(move),
                    band=band,
                    patterns=group_positions(targets, others),
                )
            )
    return tuple(rules)


@cache
def generated_rules() -> tuple[GeneratedRule, ...]:
    """The generated action rules over every valid position of one vendor."""
    return rules_from(vendor_points())
