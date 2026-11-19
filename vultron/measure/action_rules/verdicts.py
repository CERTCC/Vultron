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
"""Move advice for one vendor: each allowed move's band in that vendor's scope
alone (ADR-0216, SHD-05-007).

A move's **band for one vendor** is ADR-0200's band over that vendor's parts
only: harm-free when its deciding part (its end part, or its embargo part
when the end part is zero) is positive, unhelpful when it is not.  The parts
come from the standing record's own changes (:func:`.scope_shift`) and the
band from :func:`.band`, so no move is scored a second time.

Two readings give each vendor's moves:

* :func:`case_points` reads a live case's
  :class:`~vultron.measure.standing.StandingRecord`, so each vendor's band
  comes from the case's own outcome shifts (ADR-0216, SHD-05-011).
* :func:`vendor_points` walks the one-vendor joint model and gives every
  valid position of one vendor, each with the moves the state machines allow
  there, scored as move advice scores them (ADR-0216, SHD-05-007).  A
  position's value depends on the walk that reached it as well as on the
  position (``WalkPrefix``), so each position is read at the first walk that
  reaches it, breadth first: its shortest history.  At some positions a
  longer walk gives a move another band (``em.accept`` and ``em.reject`` at
  EM PROPOSED or REVISE, ``rm.accept`` at RM DEFERRED); which walk a
  position's verdict reads is an open decision on #6676.  A live case reads
  its own history, so :func:`case_points` has no such choice.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction
from functools import cache

from pydantic import BaseModel, ConfigDict, model_validator

from vultron.core.states.cs import CS, CS_d, CS_vf
from vultron.core.states.cs_invariants import CSEvent, cs_from_dimensions
from vultron.core.states.em import EM
from vultron.core.states.rm import RM, RM_Trigger
from vultron.enums.roles import CVDRole
from vultron.measure.action_rules.model import (
    Position,
    desideratum_name,
    move_advice_desiderata,
)
from vultron.measure.advice.bands import Band, Part, band, deciding_parts
from vultron.measure.advice.case import AllowedMove, unbanded_reason
from vultron.measure.advice.shifts import scope_shift
from vultron.measure.baselines import (
    ONE_VENDOR_MODEL,
    VendorDesideratum,
    WalkPrefix,
    desideratum_by_notation,
)
from vultron.measure.standing import (
    ScoredMove,
    StandingRecord,
    cs_moves,
    em_moves,
    rm_moves,
    scored_move,
)
from vultron.measure.standing.joint import CasePrefix
from vultron.primitives import NonEmptyString

_RECEIVE = f"rm.{RM_Trigger.RECEIVE}"

VENDOR = "vendor"
"""The one vendor of :func:`vendor_points`."""


class VendorScore(BaseModel):
    """A move's band for one vendor, and what decides it.

    Fields:
        band: Harm-free or unhelpful: one vendor's band is never a
            trade-off.
        deciding_part: The vendor's end part, or its embargo part when the
            end part is zero.
        deciding_size: That part's size.
        changes: The vendor's change in each desideratum of the move-advice
            list, by plain name.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    band: Band
    deciding_part: Part
    deciding_size: Fraction
    changes: Mapping[str, Fraction]

    @model_validator(mode="after")
    def _one_vendors_band(self) -> VendorScore:
        expected = Band.HARM_FREE if self.deciding_size > 0 else Band.UNHELPFUL
        if self.band is not expected:
            raise ValueError(
                f"a deciding part of {self.deciding_size} puts a move in the"
                f" {expected} band for one vendor, not {self.band}"
            )
        return self


class MoveVerdict(BaseModel):
    """One allowed move, as it bears on one vendor.

    Fields:
        move: The move, naming the participant who can make it.
        roles: The roles that participant holds.
        score: The move's band for the vendor, for a move move advice
            scores.
        unscored: Why it has no band: it keeps every state, it is a chance
            event, or the joint model holds no step for it.  Exactly one of
            *score* and *unscored* is set.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    move: AllowedMove
    roles: frozenset[CVDRole]
    score: VendorScore | None = None
    unscored: NonEmptyString | None = None

    @model_validator(mode="after")
    def _scored_or_says_why_not(self) -> MoveVerdict:
        if (self.score is None) == (self.unscored is None):
            raise ValueError(
                "a verdict holds a band or the reason it has none"
            )
        return self


class VendorPoint(BaseModel):
    """One vendor's position and the verdict on each move it allows.

    Fields:
        position: The vendor's position.
        verdicts: Each allowed move that bears on the vendor: its own RM and
            CS moves, and every participant's EM moves, in the record's
            order.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    position: Position
    verdicts: tuple[MoveVerdict, ...] = ()


def vendor_score(scored: ScoredMove, vendor: str) -> VendorScore | None:
    """*scored*'s band for *vendor* alone; ``None`` for a move move advice
    gives no band (:func:`.unbanded_reason`)."""
    if unbanded_reason(scored) is not None or scored.changes is None:
        return None
    readings: dict[VendorDesideratum, Fraction] = {
        VendorDesideratum(desideratum_by_notation(c.notation), 1): c.change
        for c in scored.changes
        if c.vendor == vendor and c.other_vendor is None
    }
    shift = scope_shift(readings, 1)
    part, (size,) = deciding_parts(shift)
    listed = move_advice_desiderata()
    changes = {name: Fraction(0) for name in listed} | {
        desideratum_name(key.desideratum): reading
        for key, reading in readings.items()
        if desideratum_name(key.desideratum) in listed
    }
    return VendorScore(
        band=band(shift),
        deciding_part=part,
        deciding_size=size,
        changes=changes,
    )


def _verdict(
    scored: ScoredMove, vendor: str, roles: frozenset[CVDRole]
) -> MoveVerdict:
    score = vendor_score(scored, vendor)
    if score is not None:
        return MoveVerdict(move=scored.move, roles=roles, score=score)
    reason = unbanded_reason(scored)
    assert reason is not None, "a move with no score has a reason"
    return MoveVerdict(move=scored.move, roles=roles, unscored=reason)


def _bears_on(move: AllowedMove, vendor: str) -> bool:
    """An EM move bears on every vendor; an RM or CS move on the vendor whose
    state it moves."""
    return move.name.startswith("em.") or move.participant == vendor


def vendor_verdicts(
    scored: Iterable[ScoredMove],
    vendor: str,
    roles: Mapping[str, frozenset[CVDRole]],
) -> tuple[MoveVerdict, ...]:
    """The verdict on each of *scored* that bears on *vendor*.

    *roles* gives each participant's roles, which an EM move's participant
    holds.
    """
    return tuple(
        _verdict(s, vendor, roles.get(s.move.participant, frozenset()))
        for s in scored
        if _bears_on(s.move, vendor)
    )


def case_points(record: StandingRecord) -> tuple[VendorPoint, ...]:
    """Each vendor's position in the case *record* reads, and its verdicts.

    A vendor not yet notified stands at no fix and no deployment beside the
    case's public state, and the record lists no case-state move for it.
    Its vendor awareness is its report receipt, one step of the joint model,
    so its ``cs.vendor_becomes_aware`` takes the verdict of its
    ``rm.receive`` (:func:`_unnotified_awareness`).  The record holds no
    consent state, so a rule with a PEC part is undecided at every point
    (ADR-0216, SHD-05-003).  Empty for a record with a gap.
    """
    if record.case is None:
        return ()
    roles = {
        p.participant: frozenset(p.cvd_roles) for p in record.participants
    }
    points = []
    for vendor in record.vendors:
        standing = record.for_participant(vendor)
        assert standing is not None, "every vendor is a participant"
        state = standing.case_state or cs_from_dimensions(
            CS_vf.vf, CS_d.d, record.case.pxa
        )
        position = Position(
            vendor=vendor, rm=standing.rm, cs=state, em=record.case.em
        )
        verdicts = vendor_verdicts(record.moves, vendor, roles)
        if standing.case_state is None:
            verdicts += _unnotified_awareness(position, verdicts)
        points.append(VendorPoint(position=position, verdicts=verdicts))
    return tuple(points)


def _unnotified_awareness(
    position: Position, verdicts: Sequence[MoveVerdict]
) -> tuple[MoveVerdict, ...]:
    """The ``cs.vendor_becomes_aware`` of a vendor with no case-state
    sequence, with the verdict of its ``rm.receive``: the joint model's one
    step for both (``RM START → RECEIVED`` is vendor awareness)."""
    aware = [
        m
        for m in cs_moves(position.vendor, position.cs, position.rm)
        if m.event is CSEvent.V
    ]
    receipts = [v for v in verdicts if v.move.name == _RECEIVE]
    return tuple(
        receipt.model_copy(update={"move": move})
        for move in aware
        for receipt in receipts
    )


@cache
def _shortest_prefixes() -> Mapping[tuple[RM, CS, EM], CasePrefix]:
    """The first walk of the one-vendor model to reach each position,
    breadth first, keyed by the vendor's RM, CS and EM state."""
    start: CasePrefix = WalkPrefix(ONE_VENDOR_MODEL.initial)
    seen = {start.state}
    found: dict[tuple[RM, CS, EM], CasePrefix] = {}
    queue = deque([start])
    while queue:
        prefix = queue.popleft()
        state = prefix.state
        (vendor,) = state.vendors
        cs = cs_from_dimensions(vendor.vf, vendor.d, state.pxa)
        found.setdefault((vendor.rm, cs, state.em), prefix)
        for step in ONE_VENDOR_MODEL.steps(state):
            if step.state not in seen:
                seen.add(step.state)
                queue.append(prefix.then(step))
    return found


def _point(prefix: CasePrefix) -> VendorPoint:
    state = prefix.state
    (path,) = state.vendors
    cs = cs_from_dimensions(path.vf, path.d, state.pxa)
    every_role = frozenset(CVDRole)
    moves: Sequence[AllowedMove] = (
        *rm_moves(VENDOR, path.rm, path.vf, path.d),
        *cs_moves(VENDOR, cs, path.rm),
        *em_moves(VENDOR, every_role, state.em, state.pxa),
    )
    numbers = {VENDOR: 1}
    scored = [scored_move(prefix, numbers, move) for move in moves]
    return VendorPoint(
        position=Position(vendor=VENDOR, rm=path.rm, cs=cs, em=state.em),
        verdicts=vendor_verdicts(scored, VENDOR, {VENDOR: every_role}),
    )


@cache
def vendor_points() -> tuple[VendorPoint, ...]:
    """Every valid position of one vendor, and the verdict on each move it
    allows (ADR-0216, SHD-05-007).

    The vendor holds every role, so every EM move is listed for it.  A
    position holds no consent state: the chance model has none (ADR-0216,
    SHD-06-007).  In the order a breadth-first walk first reaches each.
    """
    return tuple(_point(p) for p in _shortest_prefixes().values())


def point_prefix(position: Position) -> CasePrefix:
    """The walk :func:`vendor_points` reads *position* at.

    Raises:
        KeyError: *position* is not a valid position of one vendor.
    """
    return _shortest_prefixes()[(position.rm, position.cs, position.em)]
