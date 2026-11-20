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


"""The case narrative on the page: one line per ledger entry, naming who
did what, when, and which states it changed, each with its hindsight mark:
the step it took, graded against the move advice open just before it
(#6672).
"""

from __future__ import annotations

import streamlit as st

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.states.cs_invariants import CSEvent
from vultron.measure.advice import CaseAdvice
from vultron.shadow.analysis import (
    CaseAnalysis,
    ledger_advice,
    narrative_marks,
)
from vultron.shadow.dashboard import view
from vultron.shadow.dashboard.page.common import _styled_table

#: What the case narrative's table holds.
NARRATIVE_NOTE = (
    "Who did what, when, and which states it changed: one line per ledger"
    " entry, in ledger order, read from the ledger. The time is the one the"
    " actor's activity claims; the Case Manager's commit stamp shows only"
    " where it differs. A state shown as ? is one the source never records."
)

#: How the narrative's hindsight marks read (#6672).
HINDSIGHT_NOTE = (
    "Hindsight grades each step against the move advice open just before"
    " it: ⭐ best, 👍 good, ⚠️ sub-optimal, ➖ neutral, 👎 bad. 🎲 is an"
    " event no participant chooses and 💬 an act that is not a move; neither"
    " is graded. A best, good or sub-optimal mark takes its layer's shade on"
    " its band's legend."
)

#: What the page says while it grades the narrative's steps.
GRADING_NOTE = "Grading each step against the move advice open before it…"

#: How many ledger prefixes' move advice the page keeps across draws.
_ADVICE_CACHE_ENTRIES = 1024


# A case's first entries are the same in every longer reading of it, so a
# rerun, a followed case's next reading and another session's reading of the
# same case work out only the prefixes not seen yet.  The bound keeps a long
# follow from holding the advice of every prefix it graded.  Each draw asks
# for the prefixes in ledger order, so a case with more entries that change
# a state than the bound evicts each prefix before its next draw asks again
# and works every one out anew: about 0.2 s of CPU each.
@st.cache_data(max_entries=_ADVICE_CACHE_ENTRIES, show_spinner=False)
def _advice_of(
    entries: tuple[CaseLedgerEntry, ...], unobservable: frozenset[CSEvent]
) -> CaseAdvice | None:
    """The move advice at the last of *entries*, kept for the next draw."""
    return ledger_advice(entries, unobservable)


def _show_narrative(analysis: CaseAnalysis) -> None:
    """The case narrative: one line per ledger entry, in ledger order, each
    with its hindsight mark in its band's shade."""
    if not analysis.narrative:
        return
    st.subheader("Case narrative")
    st.caption(NARRATIVE_NOTE)
    st.caption(HINDSIGHT_NOTE)
    with st.spinner(GRADING_NOTE):
        marks = narrative_marks(analysis.reading, _advice_of)
    rows = view.marked_narrative_rows(
        analysis.narrative,
        analysis.actor_names,
        marks,
        analysis.reading.unobservable_events,
    )
    # Only the mark's cell takes its band's shade.
    _styled_table(rows, view.mark_shades(marks), view.HINDSIGHT_COLUMN)


__all__ = [
    "GRADING_NOTE",
    "HINDSIGHT_NOTE",
    "NARRATIVE_NOTE",
]
