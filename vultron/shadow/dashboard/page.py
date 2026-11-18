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
the case's level 1 standing as a scoreboard, with its open moves in the
bands of the case's move advice (ADR-0200).  Beside the analysis it always
shows the facts the reader could not translate, the states it inferred, and
what its source never records (SHD-01-004, CRD-02-005).

A reader that can follow a case
(:class:`~vultron.shadow.readers.following.CaseFollower`), the live Vultron
case reader, is followed instead of read once: the page shows the case's new
standing after each ledger entry arrives (#6531).  The last accepted reading
is kept in session state.  A reading the reader refuses shows its error
above that reading, and a follow that ends marks it as no longer live; the
reading stays on the page either way (SHD-04-005).

Each case is handled inside :func:`~vultron.shadow.log_content.case_log_context`,
so its log records name the case and its tracker reference and never carry
its content (VSD-01-003).  Each ledger entry's record carries the entry's
activity id as its correlation id.  A followed case withholds each reading
it accepts.

The page only reads: it holds the reader and nothing that can send or write
(SHD-01-001, SHD-01-002).  A case it reads lives in the process's memory
only, and nothing of it is written to disk (SHD-01-003).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

import pandas as pd
import streamlit as st

from vultron.core.models.case_reading import CaseReading
from vultron.core.ports.case_reader import CaseReader
from vultron.errors import VultronError
from vultron.logging_correlation import correlation_context
from vultron.measure.advice import CaseAdvice, case_advice
from vultron.shadow.analysis import CaseAnalysis, analyse
from vultron.shadow.dashboard import view
from vultron.shadow.log_content import CaseLog, case_log_context
from vultron.shadow.readers.following import CaseFollower

logger = logging.getLogger(__name__)

#: The page's title, also the browser tab's.
TITLE = "Case shadow tool"

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


def forget_case() -> None:
    """Drop the case entered and the reading kept for it.

    The source menu calls this when the analyst switches sources, so a case
    read from one source is never shown as if another source gave it.  It
    runs before the page draws the case box, so the box starts empty.
    """
    st.session_state.pop(CASE_KEY, None)
    st.session_state.pop(LAST_READING_KEY, None)


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
    _show_advice(case_advice(standing), names)


def _shaded_table(band: view.BandView) -> None:
    """*band*'s moves, each row filled with its shade."""
    styles = [s.css for s in band.shades]
    # Each column takes the rows' styles in row order.
    styler = pd.DataFrame(list(band.rows)).style.apply(
        lambda _column: styles, axis=0
    )
    st.dataframe(styler, hide_index=True, width="stretch")


def _show_band(band: view.BandView) -> None:
    if not band.rows:
        st.caption(band.empty)
    elif band.shaded:
        _shaded_table(band)
    else:
        _table(band.rows, band.empty)


def _show_advice(advice: CaseAdvice, names: Mapping[str, str]) -> None:
    """The open moves in their bands, and the moves with no band (ADR-0200).

    The page lays out what :func:`case_advice` returns and computes nothing
    of its own: no combined score orders any move (SHD-03-002).
    """
    st.subheader("Move advice")
    st.caption(advice.help_text)
    st.caption(advice.harm_note)
    for band in view.band_views(advice, names):
        if band.collapsed:
            with st.expander(f"{band.title} ({len(band.rows)})"):
                _show_band(band)
        else:
            st.markdown(f"**{band.title}**")
            _show_band(band)
    st.subheader("Moves with no band")
    _table(
        view.unbanded_rows(advice, names),
        "None: every allowed move is in a band.",
    )


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


def _log_reading(case_id: str, reading: CaseReading) -> None:
    """Log what was read: the case, then each entry and its source record."""
    logger.info(
        "Read case %s: %d ledger entries, %d inferences, %d untranslated"
        " facts",
        case_id,
        len(reading.ledger),
        len(reading.inferences),
        len(reading.untranslated),
    )
    sources = {c.entry_id: c.source_record for c in reading.citations}
    for entry in reading.ledger:
        with correlation_context(activity_id=entry.log_object_id):
            logger.debug(
                "Case %s entry %s (%s) translates source record %s",
                case_id,
                entry.id_,
                entry.semantic_type,
                sources[entry.id_],
            )
    for fact in reading.untranslated:
        logger.debug(
            "Case %s source record %s not translated: %s",
            case_id,
            fact.source_record,
            fact.reason,
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
        _show_reading(reading)


def _accept(case_log: CaseLog, case_id: str, reading: CaseReading) -> None:
    """Withhold *reading*'s content from the case's records, then log it."""
    case_log.withhold(reading)
    _log_reading(case_id, reading)


def _show_reading(reading: CaseReading) -> None:
    _show_standing(analyse(reading))
    _show_reader_report(reading)


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
            _show_reading(kept_reading)
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
    "forget_case",
    "render",
]
