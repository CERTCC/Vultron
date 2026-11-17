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

"""The case shadow tool's page: one case's standing, laid out (ADR-0192).

:func:`render` asks the analyst for a case, reads it through the one
:class:`~vultron.core.ports.case_reader.CaseReader` it is given, and shows
the case's level 1 standing as a scoreboard.  Beside the analysis it always
shows the facts the reader could not translate, the states it inferred, and
what its source never records (SHD-01-004, CRD-02-005).

A reader that can follow a case
(:class:`~vultron.shadow.readers.following.CaseFollower`), the live Vultron
case reader, is followed instead of read once: the page shows the case's new
standing after each ledger entry arrives (#6531).  The last accepted reading
is kept in session state.  A reading the reader refuses shows its error
above that reading, and a follow that ends marks it as no longer live; the
reading stays on the page either way (SHD-04-005).

The page only reads: it holds the reader and nothing that can send or write
(SHD-01-001, SHD-01-002).  A case it reads lives in the process's memory
only, and nothing of it is written to disk (SHD-01-003).
"""

from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

from vultron.core.models.case_reading import CaseReading
from vultron.core.ports.case_reader import CaseReader
from vultron.errors import VultronError
from vultron.shadow.analysis import CaseAnalysis, analyse
from vultron.shadow.dashboard import view
from vultron.shadow.readers.following import CaseFollower

#: The page's title, also the browser tab's.
TITLE = "Case shadow"

#: The widget key of the case the analyst enters.
CASE_KEY = "case_id"

#: The session-state key of a followed case's last accepted reading, kept
#: with the case id it is a reading of.
LAST_READING_KEY = "last_accepted_reading"

#: What the page says of a followed case while it is live, and once not.
LIVE_NOTE = (
    "Live: the page follows the case and shows its new standing as each"
    " ledger entry arrives."
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


def _table(rows: Sequence[view.Row], empty: str) -> None:
    if rows:
        st.dataframe(list(rows), hide_index=True, width="stretch")
    else:
        st.caption(empty)


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


def _show_standing(analysis: CaseAnalysis) -> None:
    standing = analysis.standing
    if standing is None:
        st.warning(
            "The case reader translated no ledger entry, so there is no"
            " standing to show."
        )
        return
    if standing.gap is not None:
        st.error(
            "The ledger has a hole, so it gives no standing: a measure over"
            " a history with a hole is wrong, not imprecise."
        )
        for line in view.gap_lines(standing.gap):
            st.markdown(f"- {line}")
        return
    assert standing.case is not None, "a record with no gap has a case"
    names = analysis.actor_names
    columns = st.columns(4)
    columns[0].metric("Embargo", view.EM_BADGES[standing.case.em])
    for column, badge in zip(
        columns[1:], view.public_badges(standing.case.pxa), strict=True
    ):
        column.metric("Public state", badge)
    if not standing.end_confirmed:
        st.caption(
            "The ledger does not prove its last entry is the case's last:"
            " the case may have moved on since."
        )
    st.subheader("Participants")
    _table(view.participant_rows(standing.participants, names), "None.")
    st.subheader("Desiderata")
    _table(
        view.desiderata_rows(standing.participants, names),
        "No vendor has a case-state history to score yet.",
    )
    st.subheader("Open moves")
    _table(view.move_rows(standing.moves, names), "No move is open.")


def _show_reader_report(reading: CaseReading) -> None:
    st.subheader("Not translated")
    st.caption(view.NOT_TRANSLATED_NOTE)
    _table(
        view.untranslated_rows(reading),
        "None: the case reader translated every fact it read.",
    )
    st.subheader("Inferred")
    _table(
        view.inference_rows(reading), "None: the source stated every state."
    )
    st.subheader("Not observable")
    st.caption(view.UNOBSERVABLE_NOTE)
    _table(
        view.unobservable_rows(reading),
        "None: the source records every fact the analysis reads.",
    )


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
    if isinstance(reader, CaseFollower):
        _follow(reader, case_id)
        return
    try:
        reading = reader.read_case(case_id)
    except VultronError as exc:
        # A refusal that carries several problems names them all in str()
        # (EH-07-003), so the analyst sees every reason at once.
        st.error(str(exc))
        return
    _show_reading(reading)


def _show_reading(reading: CaseReading) -> None:
    _show_standing(analyse(reading))
    _show_reader_report(reading)


def _follow(follower: CaseFollower, case_id: str) -> None:
    """Show *case_id*'s standing anew after each reading the follow yields.

    The script runs for as long as the follow does.  Each accepted reading
    replaces the one shown and is kept in session state; a refusal shows
    above the last accepted reading, which stays; once the follow ends, the
    reading is marked as no longer live (SHD-04-005).  A rerun of the page
    for the same case shows the kept reading until the follow sends a new
    one.
    """
    notice = st.empty()
    problem = st.empty()
    body = st.empty()
    kept = st.session_state.get(LAST_READING_KEY)
    last: CaseReading | None = None
    if kept is not None and kept[0] == case_id:
        last = kept[1]
        notice.info(RECONNECTING_NOTE)
        with body.container():
            _show_reading(last)
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
    for item in follower.follow_case(case_id, heartbeat=heartbeat):
        if isinstance(item, CaseReading):
            last = item
            st.session_state[LAST_READING_KEY] = (case_id, item)
            notice.caption(LIVE_NOTE)
            problem.empty()
            refused = False
            with body.container():
                _show_reading(item)
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
    "CASE_KEY",
    "HEARTBEAT_KEY",
    "LAST_READING_KEY",
    "LIVE_NOTE",
    "NOT_LIVE_NOTE",
    "NO_ENTRY_NOTE",
    "RECONNECTING_NOTE",
    "TITLE",
    "WAITING_NOTE",
    "render",
]
