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


"""The page's frame: its title, the case box, and the case the analyst
enters, read once through the page's case reader or followed when the
reader can follow it.
"""

from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

from vultron.core.ports.case_reader import CaseReader
from vultron.errors import VultronError
from vultron.shadow.dashboard.page.common import logger
from vultron.shadow.dashboard.page.follow import LAST_READING_KEY, _follow
from vultron.shadow.dashboard.page.points import POINT_KEY
from vultron.shadow.dashboard.page.reading import _accept, _show_reading
from vultron.shadow.log_content import case_log_context
from vultron.shadow.readers.following import CaseFollower

#: The page's title, also the browser tab's.
TITLE = "Case shadow tool"

#: The widget key of the case the analyst enters.
CASE_KEY = "case_id"


def forget_case() -> None:
    """Drop the case entered and the reading kept for it.

    The source menu calls this when the analyst switches sources, so a case
    read from one source is never shown as if another source gave it.  It
    runs before the page draws the case box, so the box starts empty.
    """
    st.session_state.pop(CASE_KEY, None)
    st.session_state.pop(LAST_READING_KEY, None)
    st.session_state.pop(POINT_KEY, None)


def _ask_for_case(suggestions: Sequence[str]) -> str | None:
    """The case the analyst enters, or ``None`` before one is entered."""
    if suggestions:
        choice = st.selectbox(
            "Case",
            options=list(suggestions),
            index=None,
            key=CASE_KEY,
            placeholder="Pick a recorded case, or type a case id",
            accept_new_options=True,
        )
    else:
        choice = st.text_input("Case", key=CASE_KEY, placeholder="Case id")
    return choice.strip() if choice and choice.strip() else None


def render(reader: CaseReader, suggestions: Sequence[str] = ()) -> None:
    """Draw the page for the case the analyst enters, read through *reader*.

    Args:
        reader: The one case reader the run reads cases through.
        suggestions: Case ids to offer, such as the recorded ledger files a
            Vultron case reader can open; the analyst may type any other.
    """
    st.title(TITLE)
    st.caption(
        "Read-only: the page reads one case through its case reader. It"
        " sends nothing and writes nothing."
    )
    case_id = _ask_for_case(suggestions)
    if case_id is None:
        st.info("Enter a case to see where it stands.")
        return
    with case_log_context(case_id) as case_log:
        if isinstance(reader, CaseFollower):
            _follow(reader, case_id, case_log)
            return
        try:
            reading = reader.read_case(case_id)
        except VultronError as exc:
            # A refused read is the analyst's to fix, not a fault: WARNING
            # (EH-06-001).
            logger.warning("Could not read case %s: %s", case_id, exc)
            # A refusal that carries several problems names them all in
            # str() (EH-07-003), so the analyst sees every reason at once.
            st.error(str(exc))
            return
        _accept(case_log, case_id, reading)
        _show_reading(reading, case_id)


__all__ = [
    "CASE_KEY",
    "TITLE",
    "forget_case",
    "render",
]
