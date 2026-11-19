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
  comes from the case's own outcome shifts and its own history (ADR-0216,
  SHD-05-011).
* :func:`vendor_points` walks the one-vendor joint model and gives every
  valid position of one vendor, each with the moves the state machines allow
  there, scored as move advice scores them (ADR-0216, SHD-05-007).  Move
  advice reads a position's history as well as its states, but only through
  which desiderata are still open: one already met or broken changes by
  nothing.  So the walk gives one point for each position and each set of
  desiderata a history can leave open there (:func:`open_desiderata`), read
  at the first walk, breadth first, that reaches it (#6676, D6).

A verdict on the event an ephemeral state forces next, such as P beside a
public exploit, is marked forced: it comes next whatever anyone does.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction
from functools import cache

from pydantic import BaseModel, ConfigDict, model_validator

from vultron.core.states.cs import CS, CS_d, CS_vf
from vultron.core.states.cs_invariants import (
    CSEvent,
    cs_from_dimensions,
    required_next_cs_events,
)
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
    Event,
    ModelName,
    VendorDesideratum,
    WalkPrefix,
    desideratum_by_notation,
)
from vultron.measure.baselines.desiderata import JOINT_TO_CS
from vultron.measure.standing import (
    CSMove,
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
        forced: Whether the move's event is the one the vendor's ephemeral
            state forces next (CSB-17-009, CSB-17-012), so it comes whatever
            anyone does.
        score: The move's band for the vendor, for a move move advice
            scores.
        unscored: Why it has no band: it keeps every state, it is a chance
            event, or the joint model holds no step for it.  Exactly one of
            *score* and *unscored* is set.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    move: AllowedMove
    roles: frozenset[CVDRole]
    forced: bool = False
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
        open_desiderata: For a point of :func:`vendor_points`, the
            move-advice desiderata still open there, by plain name, in
            catalog order; ``None`` for a live case's point, which reads the
            case's own history.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    position: Position
    verdicts: tuple[MoveVerdict, ...] = ()
    open_desiderata: tuple[NonEmptyString, ...] | None = None


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


def _forced(move: AllowedMove, state: CS) -> bool:
    return isinstance(move, CSMove) and move.event in required_next_cs_events(
        state
    )


def _verdict(
    scored: ScoredMove, vendor: str, roles: frozenset[CVDRole], state: CS
) -> MoveVerdict:
    forced = _forced(scored.move, state)
    score = vendor_score(scored, vendor)
    if score is not None:
        return MoveVerdict(
            move=scored.move, roles=roles, forced=forced, score=score
        )
    reason = unbanded_reason(scored)
    assert reason is not None, "a move with no score has a reason"
    return MoveVerdict(
        move=scored.move, roles=roles, forced=forced, unscored=reason
    )


def _bears_on(move: AllowedMove, vendor: str) -> bool:
    """An EM move bears on every vendor; an RM or CS move on the vendor whose
    state it moves."""
    return move.name.startswith("em.") or move.participant == vendor


def vendor_verdicts(
    scored: Iterable[ScoredMove],
    vendor: str,
    roles: Mapping[str, frozenset[CVDRole]],
    state: CS,
) -> tuple[MoveVerdict, ...]:
    """The verdict on each of *scored* that bears on *vendor*, whose compound
    case state is *state*.

    *roles* gives each participant's roles, which an EM move's participant
    holds.
    """
    return tuple(
        _verdict(s, vendor, roles.get(s.move.participant, frozenset()), state)
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
        verdicts = vendor_verdicts(record.moves, vendor, roles, state)
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
        receipt.model_copy(
            update={"move": move, "forced": _forced(move, position.cs)}
        )
        for move in aware
        for receipt in receipts
    )


def _had(prefix: CasePrefix) -> frozenset[Event]:
    return frozenset(event for step in prefix.history for event in step)


def open_desiderata(prefix: CasePrefix) -> tuple[str, ...]:
    """The move-advice desiderata still open at *prefix*, by plain name.

    A desideratum ``a ≺ b`` is open while neither ``a`` nor ``b`` has
    occurred; once either has, it is met or broken and stays so, so no move
    changes it.  A six-event desideratum reads the vendor's case-state
    events.  In catalog order.
    """
    had = _had(prefix)
    cs_had = frozenset(JOINT_TO_CS[e] for e in had if e in JOINT_TO_CS)
    found = []
    for name, desideratum in move_advice_desiderata().items():
        (ordering,) = desideratum.query.orderings
        events: frozenset[object] = (
            cs_had if desideratum.model is ModelName.CASE_STATE else had
        )
        if ordering.before not in events and ordering.after not in events:
            found.append(name)
    return tuple(found)


type _PointKey = tuple[RM, CS, EM, tuple[str, ...]]


def _key(prefix: CasePrefix) -> _PointKey:
    state = prefix.state
    (vendor,) = state.vendors
    cs = cs_from_dimensions(vendor.vf, vendor.d, state.pxa)
    return (vendor.rm, cs, state.em, open_desiderata(prefix))


@cache
def _first_prefixes() -> Mapping[_PointKey, CasePrefix]:
    """The first walk of the one-vendor model, breadth first, to reach each
    position with each set of open desiderata."""
    start: CasePrefix = WalkPrefix(ONE_VENDOR_MODEL.initial)
    found: dict[_PointKey, CasePrefix] = {}
    seen = {(start.state, _key(start)[3])}
    queue = deque([start])
    while queue:
        prefix = queue.popleft()
        found.setdefault(_key(prefix), prefix)
        for step in ONE_VENDOR_MODEL.steps(prefix.state):
            after = prefix.then(step)
            node = (after.state, _key(after)[3])
            if node not in seen:
                seen.add(node)
                queue.append(after)
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
        verdicts=vendor_verdicts(scored, VENDOR, {VENDOR: every_role}, cs),
        open_desiderata=open_desiderata(prefix),
    )


@cache
def vendor_points() -> tuple[VendorPoint, ...]:
    """Every valid position of one vendor, once for each set of desiderata a
    history can leave open there, with the verdict on each move it allows
    (ADR-0216, SHD-05-007).

    The vendor holds every role, so every EM move is listed for it.  A
    position holds no consent state: the chance model has none (ADR-0216,
    SHD-06-007).  In the order a breadth-first walk first reaches each.
    """
    return tuple(_point(p) for p in _first_prefixes().values())


def point_at(
    rm: RM, cs: CS, em: EM, opened: tuple[str, ...] | None = None
) -> VendorPoint:
    """The point of :func:`vendor_points` at one position, scored alone.

    *opened* picks the set of open desiderata; ``None`` takes the first a
    breadth-first walk reaches.

    Raises:
        KeyError: No walk of the one-vendor model reaches that point.
    """
    for (r, c, e, found), prefix in _first_prefixes().items():
        if (r, c, e) == (rm, cs, em) and opened in (None, found):
            return _point(prefix)
    raise KeyError(f"no walk reaches {rm} {cs.name} {em} with {opened}")


def point_prefix(point: VendorPoint) -> CasePrefix:
    """The walk :func:`vendor_points` reads *point* at.

    Raises:
        KeyError: *point* is not a point of :func:`vendor_points`.
    """
    p = point.position
    opened = point.open_desiderata
    if opened is None:
        raise KeyError("a live case's point has no walk of its own here")
    return _first_prefixes()[(p.rm, p.cs, p.em, opened)]
