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


"""A followed case: the page shows the case's new standing after each
ledger entry arrives (#6531), keeps the last accepted reading in session
state, shows a refusal above it, and marks it once the follow ends
(SHD-04-003, SHD-04-005).
"""

from __future__ import annotations

import streamlit as st

from vultron.core.models.case_reading import CaseReading
from vultron.shadow.dashboard.page.reading import _accept, _show_reading
from vultron.shadow.log_content import CaseLog
from vultron.shadow.readers.following import CaseFollower

#: The session-state key of a followed case's last accepted reading, kept
#: with the case id it is a reading of.
LAST_READING_KEY = "last_accepted_reading"

#: What the page says of a followed case while it is live, and once not.
LIVE_NOTE = (
    "Live: the page follows the case and shows its new standing, and a new"
    " narrative line, as each ledger entry arrives. A point you picked stays"
    " put."
)
NOT_LIVE_NOTE = (
    "No longer live: the case's stream has ended. The page shows the case's"
    " last accepted reading."
)
WAITING_NOTE = "Live: waiting for the case's first ledger entry."
RECONNECTING_NOTE = (
    "Reconnecting: the page shows the case's last accepted reading until"
    " the case's stream sends it again."
)
NO_ENTRY_NOTE = (
    "No longer live: the case's stream ended before it sent any ledger"
    " entry, so there is no standing to show."
)


#: The session-state key counting the follow's heartbeats.
HEARTBEAT_KEY = "follow_heartbeats"


def _follow(follower: CaseFollower, case_id: str, case_log: CaseLog) -> None:
    """Show *case_id*'s standing anew after each reading the follow yields.

    The script runs for as long as the follow does.  Each accepted reading
    replaces the one shown and is kept in session state; a refusal shows
    above the last accepted reading, which stays; once the follow ends, the
    reading is marked as no longer live (SHD-04-005).  A rerun of the page
    for the same case shows the kept reading until the follow's replay
    reaches it, so the standing never steps back.
    """
    notice = st.empty()
    problem = st.empty()
    body = st.empty()
    kept = st.session_state.get(LAST_READING_KEY)
    last: CaseReading | None = None
    if kept is not None and kept[0] == case_id:
        kept_reading: CaseReading = kept[1]
        last = kept_reading
        case_log.withhold(kept_reading)
        notice.info(RECONNECTING_NOTE)
        with body.container():
            _show_reading(kept_reading, case_id)
    else:
        st.session_state.pop(LAST_READING_KEY, None)
        notice.info(WAITING_NOTE)

    def heartbeat() -> None:
        # Streamlit checks for a stop or rerun request at each use of
        # session state, so counting a beat there lets it stop a run whose
        # page was left or asked to rerun while the case is quiet.
        st.session_state[HEARTBEAT_KEY] = (
            st.session_state.get(HEARTBEAT_KEY, 0) + 1
        )

    refused = False
    draws = 1
    # A rerun's follow replays the case from its first entry, so a kept
    # reading stays until the replay reaches it rather than stepping back.
    catching_up = last is not None
    for item in follower.follow_case(case_id, heartbeat=heartbeat):
        if isinstance(item, CaseReading):
            if (
                catching_up
                and last is not None
                and len(item.ledger) < len(last.ledger)
            ):
                continue
            catching_up = False
            last = item
            _accept(case_log, case_id, item)
            st.session_state[LAST_READING_KEY] = (case_id, item)
            notice.caption(LIVE_NOTE)
            problem.empty()
            refused = False
            with body.container():
                _show_reading(item, case_id, draws)
            draws += 1
        else:
            refused = True
            problem.error(str(item))
    if last is not None:
        notice.warning(NOT_LIVE_NOTE)
    elif refused:
        notice.empty()
    else:
        notice.warning(NO_ENTRY_NOTE)


__all__ = [
    "HEARTBEAT_KEY",
    "LAST_READING_KEY",
    "LIVE_NOTE",
    "NOT_LIVE_NOTE",
    "NO_ENTRY_NOTE",
    "RECONNECTING_NOTE",
    "WAITING_NOTE",
]
