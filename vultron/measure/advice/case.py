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
"""The move advice for one case, as the case shadow tool shows it (ADR-0200).

:func:`case_advice` reads a :class:`~vultron.measure.standing.StandingRecord`
and puts each of its open moves in a band, with its layer, its marks and its
negative parts by vendor.  The record it returns holds everything the page
shows: the bands in page order, a named colour map for each shaded band, the
help text and the note on negative shifts, so the page can render it without
recomputing anything (#6369, AC-5 as reworded for Epic #6367).

An *open move* is an allowed move that is a step of the case's joint model,
so it has an outcome shift for each vendor.  The bands, layers and marks come
from :mod:`vultron.measure.advice.bands`; the shifts are the standing
record's changes in expected outcome summed into each vendor's scope
(:func:`~vultron.measure.advice.shifts.scope_shift`).  Every other allowed
move is listed as :class:`UnbandedMove`, with the reason it has no band.

The advice writes nothing: no move it weighs is written to a ledger or a
store (CEH-01-002).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from fractions import Fraction
from functools import cache

from pydantic import BaseModel, ConfigDict, computed_field, model_validator

from vultron.enums.roles import CVDRole
from vultron.measure.advice.bands import (
    BAND_ORDER,
    Band,
    MoveAdvice,
    Part,
    advise,
    band as band_of,
    dominates,
    harms as harms_of,
)
from vultron.measure.advice.shifts import (
    CHANCE_EVENTS,
    ScopeParts,
    ScopeShift,
    scope_shift,
)
from vultron.measure.baselines import (
    EXTENDED,
    ORIGINAL,
    Desideratum,
    EventKind,
    VendorDesideratum,
)
from vultron.measure.standing import (
    CSMove,
    EMMove,
    RMMove,
    ScoredMove,
    StandingGap,
    StandingRecord,
)
from vultron.primitives import NonEmptyString

type AllowedMove = RMMove | CSMove | EMMove

COORDINATOR_ROLES: frozenset[CVDRole] = frozenset(
    {CVDRole.CASE_OWNER, CVDRole.CASE_MANAGER}
)
"""The roles whose moves are "yours" to the analyst: the coordinator's."""

HELP_TEXT = (
    "Prefer the harm-free band; inside a band, moves at the 'better' end are"
    " dominated by no other move."
)
"""The page's advice on reading the bands and their legends (SHD-03-004)."""

HARM_NOTE = (
    "A negative shift means worse than the chance value, not a broken"
    " desideratum."
)
"""What a negative part means (ADR-0200)."""

DOMINATED_BY_HARM_FREE = (
    "A harm-free move does at least as well on every vendor's end desiderata."
)
"""Why a trade-off move that a harm-free move dominates is not top."""

KEEPS_EVERY_STATE = (
    "The move keeps every state, so it shifts no outcome: it is advice, not"
    " a step."
)
"""Why a move that keeps every state has no band."""

CHANCE_EVENT = (
    "No participant chooses this event; the chance value already counts it."
)
"""Why a public exploit or observed attacks has no band."""


class ColourMap(StrEnum):
    """A named sequential colour map, perceptually uniform and colour-blind
    safe, from matplotlib.

    Each map runs from dark at its low end to light at its high end; the
    page puts layer 1 at the low, dark end.
    """

    VIRIDIS = "viridis"
    CIVIDIS = "cividis"


BAND_COLOUR_MAPS: Mapping[Band, ColourMap] = {
    Band.HARM_FREE: ColourMap.VIRIDIS,
    Band.TRADE_OFF: ColourMap.CIVIDIS,
}
"""The colour map that shades each band's layers.  The unhelpful band has
none: it is not shaded."""


class VendorShift(BaseModel):
    """One vendor's end part and embargo part of a move's outcome shift.

    Fields:
        vendor: The vendor whose scope the parts sum.
        end: The weighted change in the vendor's end desiderata.
        embargo: The weighted change in the vendor's embargo desiderata.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    vendor: NonEmptyString
    end: Fraction
    embargo: Fraction


class VendorHarm(BaseModel):
    """One negative part of a move's outcome shift, with its vendor.

    Fields:
        vendor: The vendor whose part it is.
        part: The end part or the embargo part.
        size: The part, below zero: how far the move leaves the vendor below
            the chance value.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    vendor: NonEmptyString
    part: Part
    size: Fraction

    @model_validator(mode="after")
    def _below_zero(self) -> VendorHarm:
        if self.size >= 0:
            raise ValueError(f"a harm is a negative part, not {self.size}")
        return self


class AdvisedMove(BaseModel):
    """One open move, as the page shows it in its band.

    Fields:
        move: The move, naming the participant who can make it.
        shift: Each vendor's end and embargo part, in the record's vendor
            order.
        band: The band its own shift sets.
        layer: Its depth in the dominance order over every open move, layer
            1 better; ``None`` in the unhelpful band, which is not shaded.
        top: A harm-free or trade-off move in layer 1; the page marks it
            with an icon.
        leading_among_yours: A coordinator's harm-free or trade-off move that
            none of the coordinator's other open moves dominates.
        harms: Each negative end and embargo part, by vendor.
        dominated_by_harm_free: For a trade-off move that a harm-free move
            dominates, the message that says why it is not top.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    move: AllowedMove
    shift: tuple[VendorShift, ...]
    band: Band
    layer: int | None
    top: bool
    leading_among_yours: bool
    harms: tuple[VendorHarm, ...] = ()
    dominated_by_harm_free: NonEmptyString | None = None

    @model_validator(mode="after")
    def _marks_fit_the_band(self) -> AdvisedMove:
        problems: list[str] = []
        shaded = self.band is not Band.UNHELPFUL
        if shaded and (self.layer is None or self.layer < 1):
            problems.append(
                "a harm-free or trade-off move has a layer of 1 up"
            )
        if not shaded and self.layer is not None:
            problems.append("an unhelpful move has no layer")
        if self.top and (not shaded or self.layer != 1):
            problems.append("a top move is a shaded move in layer 1")
        if self.leading_among_yours and not shaded:
            problems.append("an unhelpful move is never leading among yours")
        if self.dominated_by_harm_free is not None and (
            self.band is not Band.TRADE_OFF or self.top
        ):
            problems.append(
                "only a trade-off move that is not top says a harm-free move"
                " dominates it"
            )
        problems.extend(self._agrees_with_its_shift())
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def _agrees_with_its_shift(self) -> list[str]:
        """The band and harms the shift sets, where they differ from the
        record's (:func:`.bands.band`, :func:`.bands.harms`)."""
        parts = tuple(ScopeParts(s.end, s.embargo) for s in self.shift)
        problems: list[str] = []
        if (found := band_of(parts)) is not self.band:
            problems.append(f"its shift puts it in the {found} band")
        vendors = [s.vendor for s in self.shift]
        expected = [
            (vendors[h.vendor - 1], h.part, h.size) for h in harms_of(parts)
        ]
        if [(h.vendor, h.part, h.size) for h in self.harms] != expected:
            problems.append("its harms are not its shift's negative parts")
        return problems


class UnbandedMove(BaseModel):
    """An allowed move that is not an open move, so it has no band.

    Fields:
        move: The move.
        reason: Why it has no outcome shift.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    move: AllowedMove
    reason: NonEmptyString


class BandAdvice(BaseModel):
    """One band, as the page shows it.

    Fields:
        band: The band.
        colour_map: The map that shades its moves by layer; ``None`` for the
            unhelpful band.
        collapsed: Whether the page shows it as a closed group the analyst
            can open: only the unhelpful band.
        moves: Its moves, in no order of merit (ADR-0200).  Empty when
            no open move falls in it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    band: Band
    colour_map: ColourMap | None
    collapsed: bool
    moves: tuple[AdvisedMove, ...] = ()

    @model_validator(mode="after")
    def _shaded_unless_unhelpful(self) -> BandAdvice:
        problems: list[str] = []
        unhelpful = self.band is Band.UNHELPFUL
        if (self.colour_map is None) != unhelpful:
            problems.append("only the unhelpful band has no colour map")
        if self.collapsed != unhelpful:
            problems.append("only the unhelpful band is collapsed")
        problems.extend(
            f"{m.move.name} is a {m.band} move, not a {self.band} one"
            for m in self.moves
            if m.band is not self.band
        )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @classmethod
    def of(cls, band: Band, moves: Sequence[AdvisedMove]) -> BandAdvice:
        """*band*, holding those of *moves* that fall in it."""
        return cls(
            band=band,
            colour_map=BAND_COLOUR_MAPS.get(band),
            collapsed=band is Band.UNHELPFUL,
            moves=tuple(m for m in moves if m.band is band),
        )


class CaseAdvice(BaseModel):
    """The move advice for one case (ADR-0200), ready for the page.

    Fields:
        case_id: The case.
        end_confirmed: Whether the ledger proves nothing follows its last
            entry (:attr:`StandingRecord.end_confirmed`).
        gap: The holes that keep the ledger from a reading, or ``None``.  A
            record with a gap advises nothing.
        vendors: The vendors, one scope each, in the order each move's
            :attr:`AdvisedMove.shift` lists them.
        bands: The harm-free, trade-off and unhelpful bands, in that order;
            empty when *gap* is set.
        unbanded: Every allowed move that is not an open move, with why.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: NonEmptyString
    end_confirmed: bool
    gap: StandingGap | None = None
    vendors: tuple[NonEmptyString, ...] = ()
    bands: tuple[BandAdvice, ...] = ()
    unbanded: tuple[UnbandedMove, ...] = ()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def help_text(self) -> str:
        """The page's advice on reading the bands."""
        return HELP_TEXT

    @computed_field  # type: ignore[prop-decorator]
    @property
    def harm_note(self) -> str:
        """What a negative shift means, for the page to say."""
        return HARM_NOTE

    @model_validator(mode="after")
    def _a_reading_or_its_gap(self) -> CaseAdvice:
        problems: list[str] = []
        if self.gap is not None and (
            self.vendors or self.bands or self.unbanded
        ):
            problems.append("advice over a ledger with a gap holds no reading")
        if self.gap is None and tuple(b.band for b in self.bands) != (
            BAND_ORDER
        ):
            problems.append(
                "the bands are harm-free, trade-off and unhelpful, in order"
            )
        vendors = set(self.vendors)
        if len(vendors) != len(self.vendors):
            problems.append("a vendor is listed more than once")
        problems.extend(
            f"{m.move.name} by {m.move.participant} has a shift for another"
            " set of vendors"
            for b in self.bands
            for m in b.moves
            if tuple(s.vendor for s in m.shift) != self.vendors
        )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def band(self, band: Band) -> BandAdvice:
        """The advice's *band*.

        Raises:
            KeyError: The advice holds no bands: its ledger has a gap.
        """
        for found in self.bands:
            if found.band is band:
                return found
        raise KeyError(f"advice for {self.case_id} holds no {band} band")

    @property
    def moves(self) -> tuple[AdvisedMove, ...]:
        """Every open move, band by band."""
        return tuple(m for b in self.bands for m in b.moves)

    @property
    def deepest_layer(self) -> int:
        """The deepest layer of any harm-free or trade-off move, which every
        shaded band's legend runs to; 1 when no move has a layer."""
        return max(
            (m.layer for m in self.moves if m.layer is not None), default=1
        )


@cache
def _desiderata_by_notation() -> dict[str, Desideratum]:
    found: dict[str, Desideratum] = {}
    for desideratum in (*ORIGINAL, *EXTENDED):
        if desideratum.notation in found:
            raise ValueError(f"two desiderata print as {desideratum.notation}")
        found[desideratum.notation] = desideratum
    return found


def _desideratum(notation: str) -> Desideratum:
    try:
        return _desiderata_by_notation()[notation]
    except KeyError:
        raise ValueError(f"no desideratum prints as {notation}") from None


def _shift(scored: ScoredMove, numbers: Mapping[str, int]) -> ScopeShift:
    """*scored*'s changes summed into each vendor's scope.

    Raises:
        ValueError: A change names a desideratum or a vendor the case does
            not hold.
    """
    assert scored.changes is not None, "only a scored move has a shift"
    readings: dict[VendorDesideratum, Fraction] = {}
    for change in scored.changes:
        try:
            vendor = numbers[change.vendor]
            other = (
                None
                if change.other_vendor is None
                else numbers[change.other_vendor]
            )
        except KeyError as exc:
            raise ValueError(
                f"{exc.args[0]} is not a vendor of the case"
            ) from None
        key = VendorDesideratum(_desideratum(change.notation), vendor, other)
        readings[key] = change.change
    return scope_shift(readings, len(numbers))


def _unbanded_reason(scored: ScoredMove) -> str | None:
    """Why *scored* is not an open move; ``None`` for an open move."""
    if scored.advice:
        return KEEPS_EVERY_STATE
    if scored.unscored is not None:
        return scored.unscored
    move = scored.move
    if isinstance(move, CSMove) and EventKind(move.event) in CHANCE_EVENTS:
        return CHANCE_EVENT
    return None


def _coordinators(record: StandingRecord) -> frozenset[str]:
    return frozenset(
        p.participant
        for p in record.participants
        if COORDINATOR_ROLES.intersection(p.cvd_roles)
    )


def _advised(
    advice: MoveAdvice[int],
    move: AllowedMove,
    vendors: Sequence[str],
    dominated: bool,
) -> AdvisedMove:
    shaded = advice.band is not Band.UNHELPFUL
    return AdvisedMove(
        move=move,
        shift=tuple(
            VendorShift(vendor=v, end=p.end, embargo=p.embargo)
            for v, p in zip(vendors, advice.shift, strict=True)
        ),
        band=advice.band,
        layer=advice.layer if shaded else None,
        top=advice.top,
        leading_among_yours=advice.leading_among_yours,
        harms=tuple(
            VendorHarm(vendor=vendors[h.vendor - 1], part=h.part, size=h.size)
            for h in advice.harms
        ),
        dominated_by_harm_free=DOMINATED_BY_HARM_FREE if dominated else None,
    )


def case_advice(record: StandingRecord) -> CaseAdvice:
    """The move advice for the case *record* reads (ADR-0200).

    Args:
        record: Where the case stands
            (:func:`~vultron.measure.standing.case_standing`).

    Returns:
        Each open move in its band, with its layer, its marks and its
        negative parts by vendor, and every other allowed move with the
        reason it has no band.  A record with a gap yields only the gap.

    Raises:
        ValueError: A move's changes name a desideratum or a vendor the case
            does not hold.
    """
    if record.gap is not None:
        return CaseAdvice(
            case_id=record.case_id,
            end_confirmed=record.end_confirmed,
            gap=record.gap,
        )
    vendors = tuple(record.vendors)
    numbers = {vendor: n for n, vendor in enumerate(vendors, start=1)}
    unbanded: list[UnbandedMove] = []
    open_moves: list[ScoredMove] = []
    for scored in record.moves:
        reason = _unbanded_reason(scored)
        if reason is None:
            open_moves.append(scored)
        else:
            unbanded.append(UnbandedMove(move=scored.move, reason=reason))
    shifts = {i: _shift(m, numbers) for i, m in enumerate(open_moves)}
    coordinators = _coordinators(record)
    advice = advise(
        shifts, lambda i: open_moves[i].move.participant in coordinators
    )
    harm_free = [
        s for i, s in shifts.items() if advice[i].band is Band.HARM_FREE
    ]
    moves = [
        _advised(
            advice[i],
            scored.move,
            vendors,
            advice[i].band is Band.TRADE_OFF
            and any(dominates(s, shifts[i]) for s in harm_free),
        )
        for i, scored in enumerate(open_moves)
    ]
    return CaseAdvice(
        case_id=record.case_id,
        end_confirmed=record.end_confirmed,
        vendors=vendors,
        bands=tuple(BandAdvice.of(band, moves) for band in BAND_ORDER),
        unbanded=tuple(unbanded),
    )
