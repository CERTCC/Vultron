#!/usr/bin/env python

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


"""The move advice's bands as the page lays them out (ADR-0200): each band
in its order, each move shaded by its layer and marked as the advice marks
it, each vendor's harm on its own, and the allowed moves with no band.

No column combines the vendors' numbers into one score, and nothing here
reorders a move (SHD-03-002).
"""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction

from pydantic import BaseModel, ConfigDict, model_validator

from vultron.measure.advice import (
    AdvisedMove,
    Band,
    BandAdvice,
    CaseAdvice,
)
from vultron.measure.advice.case import AllowedMove
from vultron.shadow.dashboard.view.labels import Row, actor_label
from vultron.shadow.dashboard.view.shades import Shade, band_legend_shades


def _move_label(move: AllowedMove) -> tuple[str, str]:
    machine, _, trigger = move.name.partition(".")
    return machine.upper(), trigger.replace("_", " ").capitalize()


def _move_cells(move: AllowedMove, names: Mapping[str, str]) -> Row:
    """Who makes *move*, in which machine, and from which state to which."""
    machine, label = _move_label(move)
    return {
        "Who": actor_label(move.participant, names),
        "Machine": machine,
        "Move": label,
        "From → to": f"{move.source.name} → {move.destination.name}",
    }


#: Each band's heading on the page.
BAND_TITLES: Mapping[Band, str] = {
    Band.HARM_FREE: "Harm-free",
    Band.TRADE_OFF: "Trade-off",
    Band.UNHELPFUL: "Unhelpful",
}

#: Each band's caption when no open move falls in it.
BAND_EMPTY: Mapping[Band, str] = {
    Band.HARM_FREE: "No open move helps a vendor and harms none.",
    Band.TRADE_OFF: "No open move helps one vendor at another's cost.",
    Band.UNHELPFUL: "No open move is unhelpful.",
}

#: The icon a top move carries: a harm-free or trade-off move in layer 1.
TOP_MARK = "⭐ top"

#: The mark on a coordinator's move none of its other moves dominates.
LEADING_MARK = "👉 leading among yours"


def _size(size: Fraction) -> str:
    return f"{float(size):.3g}".replace("-", "−")


def harm_text(move: AdvisedMove, names: Mapping[str, str]) -> str:
    """Each negative part of *move*'s shift, by vendor, with its size."""
    return (
        "; ".join(
            f"{actor_label(h.vendor, names)}: {h.part} {_size(h.size)}"
            for h in move.harms
        )
        or "none"
    )


class BandView(BaseModel):
    """One band of the move advice, as the page lays it out.

    Fields:
        band: The band.
        title: Its heading.
        collapsed: Whether the page shows it as a closed group.
        rows: One row per move, in the advice's order.
        shades: Each row's shade, in row order: one per row in the
            harm-free and trade-off bands, none in the unhelpful band.
        legend: The band's legend, one shade per layer from layer 1 to
            the deepest, each the shade its layer's rows take
            (SHD-03-003); none in the unhelpful band.
        empty: What the page says when *rows* is empty.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    band: Band
    title: str
    collapsed: bool
    rows: tuple[Row, ...]
    shades: tuple[Shade, ...] = ()
    legend: tuple[Shade, ...] = ()
    empty: str

    @property
    def shaded(self) -> bool:
        """Whether its rows are shaded by layer: all but the unhelpful band."""
        return self.band is not Band.UNHELPFUL

    @model_validator(mode="after")
    def _a_shade_for_every_row_or_none(self) -> BandView:
        """A shaded band has one shade per row; the unhelpful band none."""
        if not self.shaded:
            if self.shades:
                raise ValueError("the unhelpful band is not shaded")
        elif len(self.shades) != len(self.rows):
            raise ValueError(
                f"{len(self.shades)} shades for {len(self.rows)} rows"
            )
        return self

    @model_validator(mode="after")
    def _a_legend_holding_every_row_shade(self) -> BandView:
        """A shaded band has a legend that holds each of its rows' shades;
        the unhelpful band has none."""
        problems: list[str] = []
        if not self.shaded:
            if self.legend:
                problems.append("the unhelpful band has no legend")
        else:
            if not self.legend:
                problems.append("a shaded band has a legend")
            problems.extend(
                f"row {i}'s shade {s.background} is not on the legend"
                for i, s in enumerate(self.shades)
                if s not in self.legend
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self


def _layer(move: AdvisedMove) -> int:
    assert move.layer is not None, "a move in a shaded band has a layer"
    return move.layer


def _deepest(advice: CaseAdvice) -> int:
    return max(
        (m.layer for m in advice.moves if m.layer is not None), default=1
    )


def _advised_row(
    move: AdvisedMove, band: BandAdvice, names: Mapping[str, str]
) -> Row:
    shaded = band.colour_map is not None
    row: Row = {"Layer": _layer(move)} if shaded else {}
    if shaded:
        row["Mark"] = TOP_MARK if move.top else ""
    row.update(_move_cells(move.move, names))
    if shaded:
        row["Yours"] = LEADING_MARK if move.leading_among_yours else ""
    row["Harms by vendor"] = harm_text(move, names)
    if band.band is Band.TRADE_OFF:
        row["Dominated by"] = move.dominated_by_harm_free or ""
    return row


def band_views(advice: CaseAdvice, names: Mapping[str, str]) -> list[BandView]:
    """Each band of *advice*, in its order: harm-free, trade-off, unhelpful.

    A harm-free or trade-off move is shaded by its layer in its band's
    colour map, with a mark when it is top or leading among yours; an
    unhelpful move has neither.  Each shaded band carries its legend, and
    its rows' shades are read from it (SHD-03-003).  Nothing here orders or
    scores a move: the moves keep the advice's order (SHD-03-002).
    """
    deepest = _deepest(advice)
    views = []
    for band in advice.bands:
        legend = (
            ()
            if band.colour_map is None
            else band_legend_shades(band.colour_map, deepest)
        )
        views.append(
            BandView(
                band=band.band,
                title=BAND_TITLES[band.band],
                collapsed=band.collapsed,
                rows=tuple(_advised_row(m, band, names) for m in band.moves),
                shades=tuple(legend[_layer(m) - 1] for m in band.moves)
                if legend
                else (),
                legend=legend,
                empty=BAND_EMPTY[band.band],
            )
        )
    return views


def unbanded_rows(advice: CaseAdvice, names: Mapping[str, str]) -> list[Row]:
    """One row per allowed move with no band, with the reason it has none."""
    return [
        {**_move_cells(u.move, names), "Why no band": u.reason}
        for u in advice.unbanded
    ]


__all__ = [
    "BAND_EMPTY",
    "BAND_TITLES",
    "LEADING_MARK",
    "TOP_MARK",
    "BandView",
    "band_views",
    "harm_text",
    "unbanded_rows",
]
