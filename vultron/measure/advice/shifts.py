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

"""Each vendor's scope, and a move's outcome shift in it (ADR-0200 rules 1 to 3).

A scope is one vendor of the case, notified or not.  It holds the
desiderata about that vendor: the twelve original ones, the report-handling
ones and the embargo ones, each weighted ``1 − f_d`` as the case scores
weigh them (:func:`.history_score`).  The multi-party group is left out:
``V_i ≺ F_j`` because move advice does not use it (#6502), and
``F_i ≺ P`` because the original ``F ≺ P`` already holds it for the vendor.

Each scope has two parts.  The *end* part sums the end desiderata, every
desideratum of the scope but the embargo ones; the *embargo* part sums the
embargo desiderata.  A scope's chance value is these sums over the expected
outcomes from where the case stands (:func:`.expected_outcomes`), and a
move's outcome shift is the same sums over its change in expected outcome
(:func:`.outcome_change`): each desideratum is taken in its own smallest
model, and a scope never entered counts as met.
"""

from collections.abc import Iterable, Mapping
from fractions import Fraction
from functools import cache
from typing import NamedTuple

from vultron.measure.baselines import (
    EXTENDED,
    ORIGINAL,
    Desideratum,
    Event,
    EventKind,
    Group,
    JointState,
    Step,
    VendorDesideratum,
    expected_outcomes,
    outcome_change,
)
from vultron.measure.baselines.desiderata import count_once, weight
from vultron.measure.baselines.values import CasePrefix, case_model
from vultron.measure.baselines.walk import Move

SCOPE_GROUPS: frozenset[Group] = frozenset(
    {Group.ORIGINAL, Group.REPORT_HANDLING, Group.EMBARGO}
)
"""The desiderata groups a vendor's scope holds (ADR-0200 rule 1)."""

CHANCE_EVENTS: frozenset[EventKind] = frozenset({EventKind.X, EventKind.A})
"""Events that no participant chooses, so no open move is one of them.

Public awareness is left in: publication is a participant's move.
"""


class ScopeParts(NamedTuple):
    """One vendor's end part and embargo part."""

    end: Fraction
    embargo: Fraction


type ScopeShift = tuple[ScopeParts, ...]
"""One :class:`ScopeParts` for each vendor of the case, vendor 1 first."""


@cache
def scope_desiderata() -> frozenset[Desideratum]:
    """The desiderata each vendor's scope sums, each equivalent group once.

    Those of the :data:`SCOPE_GROUPS`, less each one equivalent to one
    before it (:func:`.count_once`): ``E ≺ P`` stands for the three ``E``
    desiderata and ``Ex_own ≺ P`` for the three ``Ex_own`` ones.  Computed
    on first use: finding the equivalent pairs walks the model.
    """
    return frozenset(
        count_once(
            d for d in (*ORIGINAL, *EXTENDED) if d.group in SCOPE_GROUPS
        )
    )


@cache
def _weight(key: VendorDesideratum) -> Fraction:
    return weight(key.desideratum)


def _in_scope(key: VendorDesideratum) -> bool:
    return key.desideratum in scope_desiderata()


def _by_scope(
    readings: Mapping[VendorDesideratum, Fraction], vendor_count: int
) -> ScopeShift:
    """*readings* summed into each vendor's end and embargo parts, each weighted."""
    end = [Fraction(0)] * vendor_count
    embargo = [Fraction(0)] * vendor_count
    for key, reading in readings.items():
        if not _in_scope(key):
            continue
        weighted = _weight(key) * reading
        if key.desideratum.group is Group.EMBARGO:
            embargo[key.vendor - 1] += weighted
        else:
            end[key.vendor - 1] += weighted
    return tuple(ScopeParts(e, m) for e, m in zip(end, embargo, strict=True))


def chance_values(prefix: CasePrefix) -> ScopeShift:
    """Each vendor's chance value from *prefix*: its weighted expected outcomes.

    Raises:
        ValueError: ``prefix.state`` holds no vendor.
    """
    return _by_scope(expected_outcomes(prefix), len(prefix.state.vendors))


def outcome_shift(
    prefix: CasePrefix, move: Move[JointState, Event]
) -> ScopeShift:
    """Each vendor's outcome shift from the step *move* names.

    The expected outcome after the step minus the chance value, in each
    vendor's end and embargo parts.

    Raises:
        ValueError: ``prefix.state`` holds no vendor.
        VultronInvalidStateTransitionError: *move* is not one allowed step
            (:func:`.outcome_change`).
    """
    return _by_scope(outcome_change(prefix, move), len(prefix.state.vendors))


def open_moves(prefix: CasePrefix) -> tuple[Step[JointState, Event], ...]:
    """Every step a participant can take from *prefix*.

    The allowed steps of the case's joint model, less those of the
    :data:`CHANCE_EVENTS`.

    Raises:
        ValueError: ``prefix.state`` holds no vendor.
    """
    steps = case_model(len(prefix.state.vendors)).steps(prefix.state)
    return tuple(s for s in steps if s.event.kind not in CHANCE_EVENTS)


def move_shifts(
    prefix: CasePrefix, moves: Iterable[Step[JointState, Event]]
) -> dict[Step[JointState, Event], ScopeShift]:
    """Each of *moves*' outcome shift from *prefix* (:func:`outcome_shift`)."""
    return {move: outcome_shift(prefix, move) for move in moves}
