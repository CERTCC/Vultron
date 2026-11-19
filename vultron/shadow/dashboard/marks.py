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

"""The case narrative's hindsight marks, as plain rows (#6672).

Each narrative row (:func:`~vultron.shadow.dashboard.view.narrative_rows`)
gains its line's hindsight mark beside its log index, as an icon whose shape
reads without colour, and a note naming the move the mark graded and what it
adds.  A best, good or sub-optimal mark also takes the shade its layer has on
its band's legend in the advice it was graded by (:func:`mark_shades`).  No
Streamlit call is made here; the page lays the rows out.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from vultron.core.states.cs_invariants import CSEvent
from vultron.measure.advice import BAND_COLOUR_MAPS
from vultron.measure.advice.hindsight import (
    HindsightMark,
    NarrativeMark,
    owns_state,
)
from vultron.measure.history import NarrativeLine
from vultron.shadow.dashboard.view import (
    Row,
    Shade,
    actor_label,
    band_legend_shades,
    move_label,
    narrative_rows,
)

#: Each hindsight mark's icon.  No two share a shape, so a mark reads
#: without its shade.
HINDSIGHT_ICONS: Mapping[HindsightMark, str] = {
    HindsightMark.BEST: "⭐",
    HindsightMark.GOOD: "👍",
    HindsightMark.SUB_OPTIMAL: "⚠️",
    HindsightMark.NEUTRAL: "➖",
    HindsightMark.BAD: "👎",
    HindsightMark.CHANCE: "🎲",
    HindsightMark.NOT_A_MOVE: "💬",
}

#: The narrative column holding each line's hindsight mark.
HINDSIGHT_COLUMN = "Hindsight"

#: The narrative column saying which move a mark graded, and what it adds.
HINDSIGHT_NOTE_COLUMN = "Hindsight note"


def mark_label(mark: NarrativeMark) -> str:
    """*mark*'s icon and name: ``⭐ best``."""
    return f"{HINDSIGHT_ICONS[mark.mark]} {mark.mark}"


def mark_note(mark: NarrativeMark, names: Mapping[str, str]) -> str:
    """The move *mark* graded, by machine and move, with the participant
    whose state it moves, then what the mark adds, such as that a harm-free
    move did as well.

    A public-state or embargo move names no participant: it moves the
    case's state, the same step whoever made it.
    """
    parts: list[str] = []
    if mark.move is not None:
        machine, label = move_label(mark.move)
        moved = f"{machine} {label}"
        if owns_state(mark.move):
            moved += f" ({actor_label(mark.move.participant, names)})"
        parts.append(moved)
    if mark.note is not None:
        parts.append(mark.note)
    return ": ".join(parts)


def mark_shades(marks: Sequence[NarrativeMark]) -> tuple[Shade | None, ...]:
    """Each mark's shade, in mark order: for a best, good or sub-optimal
    mark, the shade its layer has on its band's legend in the advice it was
    graded by (:func:`~vultron.shadow.dashboard.view.band_legend_shades`);
    ``None`` for every other mark, which no band shades."""
    shades: list[Shade | None] = []
    for mark in marks:
        if (
            mark.band is None
            or mark.layer is None
            or mark.deepest_layer is None
        ):
            shades.append(None)
            continue
        legend = band_legend_shades(
            BAND_COLOUR_MAPS[mark.band], mark.deepest_layer
        )
        shades.append(legend[mark.layer - 1])
    return tuple(shades)


def marked_narrative_rows(
    lines: Sequence[NarrativeLine],
    names: Mapping[str, str],
    marks: Sequence[NarrativeMark],
    unobservable: frozenset[CSEvent] = frozenset(),
) -> list[Row]:
    """:func:`~vultron.shadow.dashboard.view.narrative_rows`, each row with
    its line's hindsight mark beside its log index and the mark's note as
    its last column.

    Raises:
        ValueError: *marks* are not one per line, in the lines' order.
    """
    if [m.log_index for m in marks] != [line.log_index for line in lines]:
        raise ValueError("the marks are not one per narrative line, in order")
    rows: list[Row] = []
    for row, mark in zip(
        narrative_rows(lines, names, unobservable), marks, strict=True
    ):
        log_index, *rest = row.items()
        rows.append(
            {
                log_index[0]: log_index[1],
                HINDSIGHT_COLUMN: mark_label(mark),
                **dict(rest),
                HINDSIGHT_NOTE_COLUMN: mark_note(mark, names),
            }
        )
    return rows


__all__ = [
    "HINDSIGHT_COLUMN",
    "HINDSIGHT_ICONS",
    "HINDSIGHT_NOTE_COLUMN",
    "mark_label",
    "mark_note",
    "mark_shades",
    "marked_narrative_rows",
]
