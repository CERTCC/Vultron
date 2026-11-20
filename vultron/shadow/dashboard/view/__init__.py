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


"""What the dashboard shows, as plain rows: the scoreboard's words and icons.

Every function here reads a :class:`~vultron.shadow.analysis.CaseAnalysis`
and returns strings and rows, with no Streamlit call, so what an analyst
reads is tested without a browser.  :mod:`~vultron.shadow.dashboard.page`
lays the rows out.

A state reads as an icon and a short label, so the page reads at a glance
(ADR-0192).  The open moves are read from the case's
:class:`~vultron.measure.advice.CaseAdvice` (ADR-0200): each band in its
order, each move shaded by its layer and marked as the advice marks it, and
each vendor's harm on its own.  No column combines the vendors' numbers into
one score, and nothing here reorders a move (SHD-03-002).

The case narrative reads one row per ledger entry
(:func:`narrative_rows`), each with its state changes in words, and a
case-state flag the source cannot observe shown as unknown (CRD-02-005),
and each line's hindsight mark (:func:`marked_narrative_rows`).

Each concern has its own module, and every name is imported from here:

* :mod:`~vultron.shadow.dashboard.view.labels` — the words and icons the
  rest share: a table row, event names, state badges, actor names.
* :mod:`~vultron.shadow.dashboard.view.standing` — the case's public state,
  the participants table, and the holes that keep a standing from showing.
* :mod:`~vultron.shadow.dashboard.view.desiderata` — the Desiderata table.
* :mod:`~vultron.shadow.dashboard.view.bands` — the move advice's bands.
* :mod:`~vultron.shadow.dashboard.view.shades` — each move's shade and a
  band's legend.
* :mod:`~vultron.shadow.dashboard.view.narrative` — the case narrative.
* :mod:`~vultron.shadow.dashboard.view.marks` — each narrative line's
  hindsight mark: its icon, note and shade (#6672).
* :mod:`~vultron.shadow.dashboard.view.points` — the point picker's words.
* :mod:`~vultron.shadow.dashboard.view.reader_report` — the case reader's
  report: untranslated, inferred and unobservable facts.
"""

from vultron.shadow.dashboard.view.bands import (
    BAND_EMPTY,
    BAND_TITLES,
    LEADING_MARK,
    TOP_MARK,
    BandView,
    band_views,
    harm_text,
    move_label,
    unbanded_rows,
)
from vultron.shadow.dashboard.view.desiderata import (
    DESIDERATA_NOTE,
    DESIDERATUM_BADGES,
    DESIDERATUM_EVENT_LABELS,
    desiderata_rows,
    desideratum_code,
    desideratum_label,
)
from vultron.shadow.dashboard.view.labels import (
    EM_BADGES,
    EVENT_LABELS,
    RM_BADGES,
    Row,
    actor_label,
)
from vultron.shadow.dashboard.view.marks import (
    HINDSIGHT_COLUMN,
    HINDSIGHT_ICONS,
    HINDSIGHT_NOTE_COLUMN,
    mark_label,
    mark_note,
    mark_shades,
    marked_narrative_rows,
)
from vultron.shadow.dashboard.view.narrative import (
    UNKNOWN_FLAG,
    change_text,
    cs_spelling,
    narrative_rows,
)
from vultron.shadow.dashboard.view.points import (
    LATEST_POINT,
    LATEST_POINT_LABEL,
    point_label,
    point_note,
    point_options,
)
from vultron.shadow.dashboard.view.reader_report import (
    NOT_TRANSLATED_NOTE,
    UNOBSERVABLE_NOTE,
    inference_rows,
    unobservable_rows,
    untranslated_rows,
)
from vultron.shadow.dashboard.view.shades import (
    COLOUR_STOPS,
    LEGEND_BETTER,
    LEGEND_DOMINATED,
    Shade,
    band_legend_shades,
    shade,
)
from vultron.shadow.dashboard.view.standing import (
    gap_lines,
    participant_rows,
    public_badges,
)

__all__ = [
    "BAND_EMPTY",
    "BAND_TITLES",
    "COLOUR_STOPS",
    "DESIDERATA_NOTE",
    "DESIDERATUM_BADGES",
    "DESIDERATUM_EVENT_LABELS",
    "HINDSIGHT_COLUMN",
    "HINDSIGHT_ICONS",
    "HINDSIGHT_NOTE_COLUMN",
    "LEADING_MARK",
    "LEGEND_BETTER",
    "LEGEND_DOMINATED",
    "TOP_MARK",
    "UNKNOWN_FLAG",
    "BandView",
    "Shade",
    "EM_BADGES",
    "EVENT_LABELS",
    "LATEST_POINT",
    "LATEST_POINT_LABEL",
    "NOT_TRANSLATED_NOTE",
    "RM_BADGES",
    "UNOBSERVABLE_NOTE",
    "actor_label",
    "Row",
    "band_legend_shades",
    "desiderata_rows",
    "desideratum_code",
    "desideratum_label",
    "gap_lines",
    "inference_rows",
    "band_views",
    "change_text",
    "cs_spelling",
    "narrative_rows",
    "point_label",
    "point_note",
    "point_options",
    "harm_text",
    "mark_label",
    "mark_note",
    "mark_shades",
    "marked_narrative_rows",
    "move_label",
    "shade",
    "unbanded_rows",
    "participant_rows",
    "public_badges",
    "unobservable_rows",
    "untranslated_rows",
]
