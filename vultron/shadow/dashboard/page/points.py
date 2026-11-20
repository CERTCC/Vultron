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


"""The point picker: the narrative line the analyst picks, kept in session
state by its entry's log index, so a followed case's new entries add lines
without moving it (#6671).
"""

from __future__ import annotations

import streamlit as st

from vultron.shadow.analysis import CaseAnalysis
from vultron.shadow.dashboard import view

#: The session-state key of the point the analyst picked: the case id and
#: the log index of the entry the scoreboard shows the case just after.
#: Absent while the scoreboard shows the case as it stands now.
POINT_KEY = "narrative_point"

#: The widget key of the point picker, before its draw number.  A followed
#: case draws the picker anew for each reading in one script run, and one
#: run may not draw two widgets under one key.
POINT_WIDGET_KEY = "narrative_point_picker"


def _picked_point(case_id: str, analysis: CaseAnalysis) -> int:
    """The log index the analyst picked for *case_id*, or
    :data:`~vultron.shadow.dashboard.view.LATEST_POINT`.

    A pick this reading does not reach yet shows the case as it stands now
    and stays kept for a later reading: as when the analyst views another
    case and comes back to a followed one, whose replay starts from its
    first entry with no reading kept for it.
    """
    picked = st.session_state.get(POINT_KEY)
    if picked is None or picked[0] != case_id:
        return view.LATEST_POINT
    log_index: int = picked[1]
    if any(line.log_index == log_index for line in analysis.narrative):
        return log_index
    return view.LATEST_POINT


def _remember_point(case_id: str, widget_key: str) -> None:
    """Keep the point the picker under *widget_key* now holds."""
    log_index = st.session_state[widget_key]
    if log_index == view.LATEST_POINT:
        st.session_state.pop(POINT_KEY, None)
    else:
        st.session_state[POINT_KEY] = (case_id, log_index)


def _pick_point(case_id: str, analysis: CaseAnalysis, draw: int) -> int:
    """Draw the point picker and return the point it shows.

    The picker's value is set from the kept pick before it is drawn, so a
    picker drawn anew under another key still shows the pick.
    """
    point = _picked_point(case_id, analysis)
    widget_key = f"{POINT_WIDGET_KEY}-{draw}"
    st.session_state[widget_key] = point
    st.selectbox(
        "Show the case as it stood just after",
        options=view.point_options(analysis.narrative),
        format_func=lambda log_index: view.point_label(
            log_index, analysis.narrative
        ),
        key=widget_key,
        on_change=_remember_point,
        args=(case_id, widget_key),
    )
    return point


__all__ = [
    "POINT_KEY",
    "POINT_WIDGET_KEY",
]
