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
did what, when, and which states it changed.
"""

from __future__ import annotations

import streamlit as st

from vultron.shadow.analysis import CaseAnalysis
from vultron.shadow.dashboard import view
from vultron.shadow.dashboard.page.common import _table

#: What the case narrative's table holds.
NARRATIVE_NOTE = (
    "Who did what, when, and which states it changed: one line per ledger"
    " entry, in ledger order, read from the ledger. The time is the one the"
    " actor's activity claims; the Case Manager's commit stamp shows only"
    " where it differs. A state shown as ? is one the source never records."
)


def _show_narrative(analysis: CaseAnalysis) -> None:
    """The case narrative: one line per ledger entry, in ledger order."""
    if not analysis.narrative:
        return
    st.subheader("Case narrative")
    st.caption(NARRATIVE_NOTE)
    _table(
        view.narrative_rows(
            analysis.narrative,
            analysis.actor_names,
            analysis.reading.unobservable_events,
        ),
        "None.",
    )


__all__ = [
    "NARRATIVE_NOTE",
]
