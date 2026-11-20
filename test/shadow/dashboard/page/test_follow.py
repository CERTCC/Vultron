"""The page following a case through the live reader, run headless with
Streamlit's ``AppTest`` over a scripted stream: each entry is shown as
it arrives, a point picked while following stays put as entries arrive
(#6671), and a refused entry, a dropped stream or a gone node keeps the
last reading, marked not live.

Spec: SHD-04-003, SHD-04-005.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from test.shadow.dashboard._support import RV, TIMEOUT, texts
from test.shadow.dashboard.page._support import (
    page_table,
    point_picker,
    scoreboard,
)
from test.support.ledger_stream import recording_rows
from vultron.shadow.dashboard.page import (
    END_UNCONFIRMED_NOTE,
    HEARTBEAT_KEY,
    LAST_READING_KEY,
    LIVE_NOTE,
    NO_ENTRY_NOTE,
    NOT_LIVE_NOTE,
)

#: A page following a case through the live reader over a scripted stream.
#: ``__ANSWERS__`` is replaced by one tuple of scripted answers per follow,
#: the last one repeated; ``rows`` are the rv recording's first rows, of its
#: ``every_row``.  The
#: follow is watched: after the page takes each item, the size of the
#: reading it kept is recorded in ``seen``.
_FOLLOW_PAGE = """
import json

import streamlit as st
from test.support.ledger_stream import (
    CLOSE, Dropping, Quiet, ScriptedStream, recording_rows, sse_event,
    sse_rows,
)
from test.shadow.dashboard._support import RV
from vultron.shadow.dashboard.page import LAST_READING_KEY, render

every_row = recording_rows(RV)
rows = every_row[:3]
bad = sse_event({"type": "CaseLedgerEntry"}, 1)


class Watched:
    # Follows through a fresh scripted reader, one script per follow.

    unobservable = ()

    def __init__(self, answers):
        self._answers = answers

    def read_case(self, case_id):
        raise AssertionError("a followed case is not read once")

    def follow_case(self, case_id, *, heartbeat=None):
        follows = st.session_state["follows"] = (
            st.session_state.get("follows", 0) + 1
        )
        script = self._answers[min(follows, len(self._answers)) - 1]
        reader = ScriptedStream(*script).reader(reconnects=0)
        for item in reader.follow_case(case_id, heartbeat=heartbeat):
            yield item
            kept = st.session_state.get(LAST_READING_KEY)
            st.session_state.setdefault("seen", []).append(
                len(kept[1].ledger) if kept else 0
            )


render(Watched([__ANSWERS__]))
"""


def _follow_page(answers: str) -> AppTest:
    """The follow page over *answers*, its case entered and followed."""
    case_id = recording_rows(RV)[0]["context"]
    script = _FOLLOW_PAGE.replace("__ANSWERS__", answers)
    at = AppTest.from_string(script, default_timeout=TIMEOUT).run()
    at.text_input[0].input(case_id).run()
    assert not at.exception
    return at


@pytest.mark.spec("SHD-04-005")
def test_a_followed_case_shows_its_new_standing_after_each_entry():
    """AC-4: each accepted reading is taken and shown as it arrives."""
    at = _follow_page("(sse_rows(rows) + CLOSE,)")
    assert at.session_state["seen"] == [1, 2, 3]
    case_id, kept = at.session_state[LAST_READING_KEY]
    assert case_id == recording_rows(RV)[0]["context"]
    assert len(kept.ledger) == 3
    assert "Participants" in texts(at.subheader)
    assert not at.error
    assert texts(at.warning) == [NOT_LIVE_NOTE]


@pytest.mark.spec("SHD-04-003")
def test_a_followed_case_adds_a_narrative_line_per_entry_and_keeps_the_rest():
    """#6670 AC-3: each entry that arrives adds its line; none is lost."""
    first = page_table(
        _follow_page("(sse_rows(rows[:1]) + CLOSE,)"), "Case narrative"
    )
    three = page_table(
        _follow_page("(sse_rows(rows) + CLOSE,)"), "Case narrative"
    )
    assert first["#"].tolist() == [0]
    assert three["#"].tolist() == [0, 1, 2]
    assert three.iloc[:1].equals(first)


def test_a_new_entry_does_not_move_the_picked_point():
    """#6671 AC-3: picked at #0 while following, the scoreboard stays at #0
    as the rerun's follow replays the case and new entries arrive.

    The rv recording's standing first changes at its 11th and 13th entries,
    so the case as it stands now differs from the case at #0.
    """
    at = _follow_page(
        "(sse_rows(every_row[:11]) + CLOSE,),"
        " (sse_rows(every_row[:13]) + CLOSE,)"
    )
    now = scoreboard(at)
    point_picker(at).select(0).run()
    assert not at.exception
    assert at.session_state["follows"] == 2
    # The kept reading, its replay, then the two new entries.
    assert at.session_state["seen"][-3:] == [11, 12, 13]
    assert point_picker(at).value == 0
    assert page_table(at, "Case narrative")["#"].tolist() == list(range(13))
    assert any("just after entry #0" in i for i in texts(at.info))
    one_entry = scoreboard(_follow_page("(sse_rows(rows[:1]) + CLOSE,)"))
    assert one_entry != now
    assert scoreboard(at) == one_entry


def test_a_pick_at_the_latest_entry_stops_hedging_once_entries_follow():
    """Picked at a followed case's last entry, the scoreboard hedges that
    the case may have moved on; once later entries arrive the pick is a
    past point, after which the case is known to move on, and the hedge
    goes."""
    at = _follow_page(
        "(sse_rows(every_row[:11]) + CLOSE,),"
        " (sse_rows(every_row[:13]) + CLOSE,)"
    )
    assert END_UNCONFIRMED_NOTE in texts(at.caption)
    # The first follow's last entry: the 11th, at log index 10.
    last = 10
    assert point_picker(at).options[-1].startswith(f"#{last} ")
    point_picker(at).select(last).run()
    assert not at.exception
    assert at.session_state["follows"] == 2
    assert point_picker(at).value == last
    assert page_table(at, "Case narrative")["#"].tolist() == list(range(13))
    assert END_UNCONFIRMED_NOTE not in texts(at.caption)


@pytest.mark.spec("SHD-04-005")
def test_a_refused_entry_then_close_keeps_the_last_reading_marked():
    """The first reading stays, the error shows, then it is not live."""
    at = _follow_page("(sse_rows(rows[:1]) + bad + CLOSE,)")
    assert at.session_state["seen"] == [1, 1]
    _, kept = at.session_state[LAST_READING_KEY]
    assert len(kept.ledger) == 1
    (error,) = texts(at.error)
    assert "Cannot read case" in error
    assert "log/stream line 2: not a case ledger entry" in error
    assert "Participants" in texts(at.subheader)
    assert texts(at.warning) == [NOT_LIVE_NOTE]


@pytest.mark.spec("SHD-04-005")
def test_a_dropped_stream_keeps_the_last_reading_marked_not_live():
    """No close event: the node is lost, and the reading is kept."""
    at = _follow_page("(Dropping(sse_rows(rows[:2])),)")
    assert at.session_state["seen"] == [1, 2, 2]
    _, kept = at.session_state[LAST_READING_KEY]
    assert len(kept.ledger) == 2
    (error,) = texts(at.error)
    assert "cannot be reached" in error
    assert "Participants" in texts(at.subheader)
    assert texts(at.warning) == [NOT_LIVE_NOTE]


def test_a_follow_refused_before_any_reading_shows_only_why():
    at = _follow_page('((404, json.dumps({"detail": "Case not found."})),)')
    (error,) = texts(at.error)
    assert "holds no such case" in error
    assert "Participants" not in texts(at.subheader)
    assert not at.warning
    assert not at.info
    assert LIVE_NOTE not in texts(at.caption)
    assert LAST_READING_KEY not in at.session_state


def test_a_stream_that_closes_before_any_entry_says_so():
    at = _follow_page("(CLOSE,)")
    assert not at.error
    assert texts(at.warning) == [NO_ENTRY_NOTE]
    assert "Participants" not in texts(at.subheader)


def test_a_quiet_case_beats_the_heartbeat_while_it_waits():
    """The heartbeat runs at each keepalive and each quiet reconnect."""
    at = _follow_page(
        "(Quiet(sse_rows(rows[:1]) + ': keepalive\\n\\n'),"
        " sse_rows(rows[1:2]) + CLOSE)"
    )
    assert at.session_state["seen"] == [1, 2]
    assert at.session_state[HEARTBEAT_KEY] == 2
    assert texts(at.warning) == [NOT_LIVE_NOTE]


@pytest.mark.spec("SHD-04-005")
def test_a_rerun_shows_the_kept_reading_when_the_node_is_gone():
    """The kept reading is read back: the second run's node refuses."""
    at = _follow_page(
        "(sse_rows(rows) + CLOSE,),"
        " ((404, json.dumps({'detail': 'Case not found.'})),)"
    )
    assert at.session_state["seen"] == [1, 2, 3]
    at.run()
    assert not at.exception
    assert at.session_state["follows"] == 2
    _, kept = at.session_state[LAST_READING_KEY]
    assert len(kept.ledger) == 3
    (error,) = texts(at.error)
    assert "holds no such case" in error
    assert "Participants" in texts(at.subheader)
    assert texts(at.warning) == [NOT_LIVE_NOTE]


@pytest.mark.spec("SHD-04-005")
def test_a_rerun_keeps_its_standing_while_the_follow_replays_the_case():
    """The replay of entries already shown never steps the standing back."""
    at = _follow_page("(sse_rows(rows) + CLOSE,)")
    assert at.session_state["seen"] == [1, 2, 3]
    at.run()
    assert not at.exception
    assert at.session_state["follows"] == 2
    assert at.session_state["seen"] == [1, 2, 3, 3, 3, 3]
    assert texts(at.warning) == [NOT_LIVE_NOTE]
