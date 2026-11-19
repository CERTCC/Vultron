"""The case shadow tool's page, run headless with Streamlit's ``AppTest``.

The real script over a committed recording shows the case's states,
desiderata and open moves (AC-1); the move advice reads band by band, with
its shades, marks, harms and unbanded moves (#6603); a fake reader's
untranslated facts, inferences and unobservable facts are shown beside the
analysis (AC-2); a read the reader refuses, a ledger with a hole, a reading
with no entry and a setting the reader cannot use each say so on the page.

Spec: SHD-01-002, SHD-01-004, SHD-03-002.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from streamlit.testing.v1 import AppTest

from test.support.ledger_stream import recording_rows
from vultron.config import clear_config_cache, config_override
from vultron.config.shadow import ShadowConfig
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.measure.advice import (
    CHANCE_EVENT,
    DOMINATED_BY_HARM_FREE,
    HARM_NOTE,
    HELP_TEXT,
    Band,
)
from vultron.shadow.dashboard.app import APP_PATH, ledger_suggestions
from vultron.shadow.dashboard.page import (
    END_UNCONFIRMED_NOTE,
    HEARTBEAT_KEY,
    LAST_READING_KEY,
    LIVE_NOTE,
    NARRATIVE_NOTE,
    NO_ENTRY_NOTE,
    NOT_LIVE_NOTE,
    POINT_KEY,
    TITLE,
)
from vultron.shadow.dashboard.view import (
    BAND_EMPTY,
    EM_BADGES,
    LATEST_POINT,
    LEADING_MARK,
    RM_BADGES,
    TOP_MARK,
)
from vultron.shadow.readers import CaseSource

#: Seconds one script run may take; the first run imports the measures.
_TIMEOUT = 60

_RV = RECORDINGS_DIR / "rv" / "case-actor.jsonl"

_FAKE_PAGE = """
from test.support.case_reader import FAKE_CASE, FakeCaseReader, fake_case_records
from vultron.shadow.dashboard.page import render

render(FakeCaseReader({FAKE_CASE: fake_case_records()}))
"""

_SPY_PAGE = """
import streamlit as st
from test.support.case_reader import FAKE_CASE, FakeCaseReader, fake_case_records
from vultron.shadow.dashboard.page import render


class Spy:
    def __init__(self):
        self._reader = FakeCaseReader({FAKE_CASE: fake_case_records()})
        self.unobservable = self._reader.unobservable

    def __getattr__(self, name):
        st.session_state.setdefault("touched", []).append(name)
        return getattr(self._reader, name)

    def read_case(self, case_id):
        st.session_state.setdefault("read", []).append(case_id)
        return self._reader.read_case(case_id)


render(Spy())
"""

_ADVICE_PAGE = """
from test.measure.history.builders import two_vendors_ledger
from vultron.measure.advice import case_advice
from vultron.measure.standing import case_standing
from vultron.shadow.dashboard.page import _show_advice

_show_advice(case_advice(case_standing(two_vendors_ledger().case_ledger())), {})
"""

_EMPTY_PAGE = """
from vultron.core.models.case_reading import (
    CaseReading, UntranslatedFact, UntranslatedReason,
)
from vultron.shadow.dashboard.page import render


class Empty:
    unobservable = ()

    def read_case(self, case_id):
        fact = UntranslatedFact(
            source_record="rec-9", fact="kind = mood",
            reason=UntranslatedReason.UNKNOWN_VALUE,
        )
        return CaseReading(ledger=(), citations=(), untranslated=(fact,))


render(Empty())
"""


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
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.shadow.dashboard.page import LAST_READING_KEY, render

every_row = recording_rows(RECORDINGS_DIR / "rv" / "case-actor.jsonl")
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
    case_id = recording_rows(_RV)[0]["caseId"]
    script = _FOLLOW_PAGE.replace("__ANSWERS__", answers)
    at = AppTest.from_string(script, default_timeout=_TIMEOUT).run()
    at.text_input[0].input(case_id).run()
    assert not at.exception
    return at


def _texts(elements) -> list[str]:
    return [str(element.value) for element in elements]


#: Each table's columns, which tell the tables apart.
_COLUMNS = {
    "Participants": [
        "Participant",
        "Roles",
        "Joined",
        "Report",
        "Case state",
        "Desiderata",
        "Not scored because",
        "Actor",
    ],
    "Harm-free": [
        "Layer",
        "Mark",
        "Who",
        "Machine",
        "Move",
        "From → to",
        "Yours",
        "Harms by vendor",
    ],
    "Trade-off": [
        "Layer",
        "Mark",
        "Who",
        "Machine",
        "Move",
        "From → to",
        "Yours",
        "Harms by vendor",
        "Dominated by",
    ],
    "Unhelpful": ["Who", "Machine", "Move", "From → to", "Harms by vendor"],
    "Moves with no band": [
        "Who",
        "Machine",
        "Move",
        "From → to",
        "Why no band",
    ],
    "Case narrative": [
        "#",
        "Time",
        "Committed",
        "Actor",
        "Activity",
        "Object",
        "State changes",
    ],
    "Not translated": ["Source record", "Fact", "Why"],
    "Inferred": ["Entry", "Rule", "Caveat"],
    "Not observable": ["Fact", "Why", "Reads as unknown"],
}


def _frame(at: AppTest, heading: str):
    """The dataframe element drawn under *heading*, told apart by its
    columns.

    The desiderata table's vendor columns vary, so it is the one whose
    first two columns are its own.
    """
    for frame in at.dataframe:
        columns = frame.value.columns.tolist()
        if heading == "Desiderata" and columns[:2] == [
            "Desideratum",
            "Events",
        ]:
            return frame
        if columns == _COLUMNS.get(heading):
            return frame
    raise AssertionError(f"no {heading!r} table on the page")


def _table(at: AppTest, heading: str):
    """The table drawn under *heading*, as a data frame."""
    return _frame(at, heading).value


@pytest.fixture
def recordings_app() -> Iterator[AppTest]:
    with config_override(VULTRON_SHADOW__LEDGER_DIR=str(RECORDINGS_DIR)):
        yield AppTest.from_file(str(APP_PATH), default_timeout=_TIMEOUT)


def test_the_page_asks_for_a_case_before_reading_any(recordings_app):
    at = recordings_app.run()
    assert not at.exception
    assert _texts(at.title) == [TITLE]
    assert "Enter a case to see where it stands." in _texts(at.info)
    assert "rv/case-actor.jsonl" in at.selectbox[0].options


def test_a_recorded_case_shows_its_states_desiderata_and_moves(
    recordings_app,
):
    """AC-1: entering a case shows its states, desiderata and open moves."""
    at = recordings_app.run()
    at.selectbox[0].select("rcvv-embargo/case-actor.jsonl").run()
    assert not at.exception
    metrics = _texts(at.metric)
    assert metrics[0] in EM_BADGES.values()
    assert len(metrics) == 4
    participants = _table(at, "Participants")
    assert "Vendor" in participants["Participant"].tolist()
    assert set(participants["Report"]) <= set(RM_BADGES.values())
    desiderata = _table(at, "Desiderata")
    assert len(desiderata) == 12
    assert {"Vendor", "Vendor2"} <= set(desiderata.columns)
    moves = _table(at, "Harm-free")
    assert len(moves) > 0
    assert set(moves["Machine"]) <= {"RM", "CS", "EM"}
    assert set(_table(at, "Moves with no band")["Machine"]) <= {
        "RM",
        "CS",
        "EM",
    }
    # No move of this recording trades off or is unhelpful: each band says
    # so, the unhelpful one inside its closed group.
    assert BAND_EMPTY[Band.TRADE_OFF] in _texts(at.caption)
    (unhelpful,) = at.expander
    assert _texts(unhelpful.caption) == [BAND_EMPTY[Band.UNHELPFUL]]
    # The recording ends on the CASE_MANAGER's closure: nothing follows.
    assert not any("moved on" in c for c in _texts(at.caption))


def test_a_recorded_case_shows_its_narrative_one_line_per_entry(
    recordings_app,
):
    """#6670 AC-1, AC-2: one line per ledger entry, in log-index order,
    naming who did what and which states it changed."""
    at = recordings_app.run()
    at.selectbox[0].select("rcvv-embargo/case-actor.jsonl").run()
    assert not at.exception
    assert "Case narrative" in _texts(at.subheader)
    assert NARRATIVE_NOTE in _texts(at.caption)
    narrative = _table(at, "Case narrative")
    entries = recording_rows(
        RECORDINGS_DIR / "rcvv-embargo" / "case-actor.jsonl"
    )
    assert narrative["#"].tolist() == list(range(len(entries)))
    assert narrative["Activity"].tolist()[0] == "Case Actor created the case"
    changes = " ".join(narrative["State changes"])
    assert "EM: " in changes and "VFD: " in changes and "PXA: " in changes


#: The tables a scoreboard draws, which follow the picked point.
_SCOREBOARD = ("Participants", "Harm-free", "Trade-off", "Moves with no band")


def _scoreboard(at: AppTest) -> dict[str, object]:
    """What the page's scoreboard shows: its metrics, its captions and each
    of its tables, ``None`` for one it draws empty."""
    shown: dict[str, object] = {
        "metrics": _texts(at.metric),
        # A past point does not hedge on the case's end, as a cut file must.
        "captions": [
            c for c in _texts(at.caption) if c != END_UNCONFIRMED_NOTE
        ],
    }
    for frame in at.dataframe:
        columns = frame.value.columns.tolist()
        heading = next(
            (h for h, c in _COLUMNS.items() if c == columns), columns[0]
        )
        if heading in _SCOREBOARD or heading == "Desideratum":
            shown[heading] = frame.value.to_dict("list")
    return shown


def _point_picker(at: AppTest):
    (picker,) = [box for box in at.selectbox if box.label.startswith("Show")]
    return picker


def _cut_page(tmp_path, recording, count: int) -> AppTest:
    """The page over a copy of *recording* cut after *count* entries."""
    rows = recording.read_text().splitlines()[:count]
    (tmp_path / "cut.jsonl").write_text("\n".join(rows) + "\n")
    with config_override(VULTRON_SHADOW__LEDGER_DIR=str(tmp_path)):
        at = AppTest.from_file(str(APP_PATH), default_timeout=_TIMEOUT).run()
        at.selectbox[0].select("cut.jsonl").run()
    assert not at.exception
    return at


_RCVV = RECORDINGS_DIR / "rcvv-embargo" / "case-actor.jsonl"


@pytest.mark.parametrize("log_index", [3, 30])
def test_picking_a_narrative_line_shows_the_case_just_after_it(
    recordings_app, tmp_path, log_index
):
    """#6671 AC-1: the states, desiderata and move bands at line N are the
    ones a reading of entries up to N alone shows; the narrative stays
    whole."""
    at = recordings_app.run()
    at.selectbox[0].select("rcvv-embargo/case-actor.jsonl").run()
    now = _scoreboard(at)
    picker = _point_picker(at)
    assert picker.value == LATEST_POINT
    picker.select(log_index).run()
    assert not at.exception
    assert _point_picker(at).value == log_index
    assert at.session_state[POINT_KEY] == (
        "rcvv-embargo/case-actor.jsonl",
        log_index,
    )
    assert any(f"just after entry #{log_index}" in i for i in _texts(at.info))
    at_point = _scoreboard(at)
    assert at_point != now
    assert at_point == _scoreboard(_cut_page(tmp_path, _RCVV, log_index + 1))
    entries = recording_rows(_RCVV)
    assert len(_table(at, "Case narrative")) == len(entries)


def test_picking_now_shows_where_the_case_stands_again(recordings_app):
    at = recordings_app.run()
    at.selectbox[0].select("rcvv-embargo/case-actor.jsonl").run()
    now = _scoreboard(at)
    _point_picker(at).select(3).run()
    assert _scoreboard(at) != now
    _point_picker(at).select(LATEST_POINT).run()
    assert not at.exception
    assert POINT_KEY not in at.session_state
    assert _scoreboard(at) == now
    assert not any("just after entry" in i for i in _texts(at.info))


def test_a_past_point_does_not_hedge_that_the_case_may_have_moved_on():
    """The fake case's end is unproven: its last entry hedges, and an
    earlier point, after which the case is known to move on, does not."""
    at = AppTest.from_string(_FAKE_PAGE, default_timeout=_TIMEOUT).run()
    at.text_input[0].input("urn:uuid:case-1").run()
    assert END_UNCONFIRMED_NOTE in _texts(at.caption)
    picker = _point_picker(at)
    first, *_, last = picker.options[1:]
    picker.select(last).run()
    assert not at.exception
    assert END_UNCONFIRMED_NOTE in _texts(at.caption)
    _point_picker(at).select(first).run()
    assert not at.exception
    assert END_UNCONFIRMED_NOTE not in _texts(at.caption)


@pytest.mark.parametrize(
    "kept",
    [("rv/case-actor.jsonl", 3), ("rcvv-embargo/case-actor.jsonl", 9999)],
    ids=["another case", "an entry the reading does not reach"],
)
def test_a_pick_this_reading_cannot_show_leaves_the_case_as_it_stands(
    recordings_app, kept
):
    """A pick of another case, or of an entry the reading does not hold
    yet, shows the case now; a pick of this case is kept for later."""
    at = recordings_app.run()
    at.selectbox[0].select("rcvv-embargo/case-actor.jsonl").run()
    now = _scoreboard(at)
    at.session_state[POINT_KEY] = kept
    at.run()
    assert not at.exception
    assert _point_picker(at).value == LATEST_POINT
    assert _scoreboard(at) == now
    assert at.session_state[POINT_KEY] == kept


@pytest.fixture(scope="module")
def advice_app() -> AppTest:
    """The advice section for a case with a move in every band."""
    at = AppTest.from_string(_ADVICE_PAGE, default_timeout=_TIMEOUT).run()
    assert not at.exception
    return at


def test_the_bands_are_shown_in_order_with_the_unhelpful_one_collapsed(
    advice_app,
):
    """AC-1: harm-free, trade-off, then the unhelpful band as a closed
    group the analyst can open."""
    at = advice_app
    assert _texts(at.markdown)[:2] == ["**Harm-free**", "**Trade-off**"]
    (unhelpful,) = at.expander
    assert unhelpful.label.startswith("Unhelpful (")
    assert unhelpful.proto.expanded is False
    (inside,) = unhelpful.dataframe
    assert inside.value.columns.tolist() == _COLUMNS["Unhelpful"]
    headings = _texts(at.subheader)
    assert headings == ["Move advice", "Moves with no band"]


def test_each_shaded_band_is_filled_by_layer_and_marks_top_moves(advice_app):
    """AC-2: the harm-free and trade-off rows carry their shades; the
    unhelpful band has neither shade nor mark."""
    at = advice_app
    for heading in ("Harm-free", "Trade-off"):
        styles = _frame(at, heading).proto.arrow_data.styler.styles
        assert "background-color: #" in styles
        # The layer is a number, so its column sorts as one.
        assert _table(at, heading)["Layer"].dtype.kind == "i"
    harm_free = _table(at, "Harm-free")
    assert TOP_MARK in harm_free["Mark"].tolist()
    unhelpful = _frame(at, "Unhelpful").proto.arrow_data
    assert not unhelpful.HasField("styler")


def test_the_page_shows_the_marks_help_text_and_harm_note(advice_app):
    """AC-3, AC-4, AC-5: the leading mark, the help text and the note on
    negative shifts, each vendor's harm, and the domination message."""
    at = advice_app
    captions = _texts(at.caption)
    assert HELP_TEXT in captions
    assert HARM_NOTE in captions
    assert LEADING_MARK in _table(at, "Harm-free")["Yours"].tolist()
    trade_off = _table(at, "Trade-off")
    assert all("−" in h for h in trade_off["Harms by vendor"])
    assert DOMINATED_BY_HARM_FREE in trade_off["Dominated by"].tolist()


def test_the_moves_with_no_band_are_listed_with_why(advice_app):
    """AC-6: each unbanded move, with its reason."""
    unbanded = _table(advice_app, "Moves with no band")
    assert CHANCE_EVENT in unbanded["Why no band"].tolist()


@pytest.mark.spec("SHD-01-004")
def test_the_untranslated_facts_are_shown_beside_the_analysis():
    """AC-2: a fake reader's untranslated facts are on the page."""
    at = AppTest.from_string(_FAKE_PAGE, default_timeout=_TIMEOUT).run()
    at.text_input[0].input("urn:uuid:case-1").run()
    assert not at.exception
    headings = _texts(at.subheader)
    assert headings.index("Participants") < headings.index("Not translated")
    untranslated = _table(at, "Not translated")
    assert sorted(untranslated["Source record"]) == [
        "rec-early",
        "rec-odd",
        "rec-pinned",
        "rec-untimed",
    ]
    assert set(untranslated["Why"]) == {
        "unknown value",
        "no counterpart",
        "rule conflict",
        "no time",
    }
    assert len(_table(at, "Inferred")) == 3
    assert _table(at, "Not observable")["Fact"].tolist() == [
        "Fix deployed (D)"
    ]
    # Nothing proves the fake case's last entry is its last.
    assert END_UNCONFIRMED_NOTE in _texts(at.caption)


def test_a_blank_case_is_no_case():
    at = AppTest.from_string(_FAKE_PAGE, default_timeout=_TIMEOUT).run()
    at.text_input[0].input("   ").run()
    assert not at.exception
    assert "Enter a case to see where it stands." in _texts(at.info)


@pytest.mark.spec("SHD-01-002")
def test_the_page_reads_the_case_only_through_read_case():
    at = AppTest.from_string(_SPY_PAGE, default_timeout=_TIMEOUT).run()
    at.text_input[0].input("urn:uuid:case-1").run()
    assert not at.exception
    assert at.session_state["read"] == ["urn:uuid:case-1"]
    assert "touched" not in at.session_state


def test_a_reading_with_no_entry_shows_its_report_and_no_standing():
    at = AppTest.from_string(_EMPTY_PAGE, default_timeout=_TIMEOUT).run()
    at.text_input[0].input("any").run()
    assert not at.exception
    assert any("translated no ledger entry" in w for w in _texts(at.warning))
    assert "Participants" not in _texts(at.subheader)
    assert "Case narrative" not in _texts(at.subheader)
    assert _table(at, "Not translated")["Source record"].tolist() == ["rec-9"]


def test_a_case_the_reader_refuses_shows_every_reason(tmp_path):
    (tmp_path / "bad.jsonl").write_text("not json\n{}\n")
    with config_override(VULTRON_SHADOW__LEDGER_DIR=str(tmp_path)):
        at = AppTest.from_file(str(APP_PATH), default_timeout=_TIMEOUT).run()
        at.selectbox[0].select("bad.jsonl").run()
    assert not at.exception
    (error,) = _texts(at.error)
    assert "Cannot read a case from bad.jsonl (2 violation(s))" in error
    assert "Participants" not in _texts(at.subheader)


def test_a_ledger_with_a_hole_shows_the_hole_not_a_standing(tmp_path):
    rows = (
        (RECORDINGS_DIR / "rv" / "case-actor.jsonl").read_text().splitlines()
    )
    (tmp_path / "holed.jsonl").write_text(
        "\n".join(rows[:2] + rows[3:]) + "\n"
    )
    with config_override(VULTRON_SHADOW__LEDGER_DIR=str(tmp_path)):
        at = AppTest.from_file(str(APP_PATH), default_timeout=_TIMEOUT).run()
        at.selectbox[0].select("holed.jsonl").run()
    assert not at.exception
    assert any("has a hole" in e for e in _texts(at.error))
    assert "- Missing log indices: [2]" in _texts(at.markdown)
    assert "Participants" not in _texts(at.subheader)
    assert "Not translated" in _texts(at.subheader)


def test_a_connector_that_is_not_installed_stops_the_page_with_why():
    with config_override(VULTRON_SHADOW__CONNECTOR="no-such-connector"):
        at = AppTest.from_file(str(APP_PATH), default_timeout=_TIMEOUT).run()
        at.sidebar.radio[0].set_value(CaseSource.OUTSIDE).run()
    assert not at.exception
    (error,) = _texts(at.error)
    assert "'no-such-connector'" in error
    assert not at.selectbox and not at.text_input
    # The menu stays, so the analyst can pick another source.
    assert at.sidebar.radio[0].value == CaseSource.OUTSIDE


def test_a_setting_that_does_not_load_stops_the_page_with_why(monkeypatch):
    """A blank connector fails the config load itself, inside the page."""
    monkeypatch.setenv("VULTRON_SHADOW__CONNECTOR", "")
    clear_config_cache()
    try:
        at = AppTest.from_file(str(APP_PATH), default_timeout=_TIMEOUT).run()
    finally:
        monkeypatch.delenv("VULTRON_SHADOW__CONNECTOR")
        clear_config_cache()
    assert not at.exception
    (error,) = _texts(at.error)
    assert "shadow.connector" in error
    assert not at.selectbox and not at.text_input


def test_suggestions_are_the_ledger_files_under_the_ledger_dir(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "case.jsonl").write_text("")
    (tmp_path / "b.jsonl").write_text("")
    (tmp_path / "notes.txt").write_text("")
    assert ledger_suggestions(ShadowConfig(ledger_dir=tmp_path)) == [
        "a/case.jsonl",
        "b.jsonl",
    ]


def test_with_no_ledger_dir_there_is_no_suggestion(tmp_path):
    assert ledger_suggestions(ShadowConfig()) == []
    assert ledger_suggestions(ShadowConfig(ledger_dir=tmp_path / "gone")) == []


@pytest.mark.spec("SHD-04-005")
def test_a_followed_case_shows_its_new_standing_after_each_entry():
    """AC-4: each accepted reading is taken and shown as it arrives."""
    at = _follow_page("(sse_rows(rows) + CLOSE,)")
    assert at.session_state["seen"] == [1, 2, 3]
    case_id, kept = at.session_state[LAST_READING_KEY]
    assert case_id == recording_rows(_RV)[0]["caseId"]
    assert len(kept.ledger) == 3
    assert "Participants" in _texts(at.subheader)
    assert not at.error
    assert _texts(at.warning) == [NOT_LIVE_NOTE]


@pytest.mark.spec("SHD-04-003")
def test_a_followed_case_adds_a_narrative_line_per_entry_and_keeps_the_rest():
    """#6670 AC-3: each entry that arrives adds its line; none is lost."""
    first = _table(
        _follow_page("(sse_rows(rows[:1]) + CLOSE,)"), "Case narrative"
    )
    three = _table(_follow_page("(sse_rows(rows) + CLOSE,)"), "Case narrative")
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
    now = _scoreboard(at)
    _point_picker(at).select(0).run()
    assert not at.exception
    assert at.session_state["follows"] == 2
    # The kept reading, its replay, then the two new entries.
    assert at.session_state["seen"][-3:] == [11, 12, 13]
    assert _point_picker(at).value == 0
    assert _table(at, "Case narrative")["#"].tolist() == list(range(13))
    assert any("just after entry #0" in i for i in _texts(at.info))
    one_entry = _scoreboard(_follow_page("(sse_rows(rows[:1]) + CLOSE,)"))
    assert one_entry != now
    assert _scoreboard(at) == one_entry


@pytest.mark.spec("SHD-04-005")
def test_a_refused_entry_then_close_keeps_the_last_reading_marked():
    """The first reading stays, the error shows, then it is not live."""
    at = _follow_page("(sse_rows(rows[:1]) + bad + CLOSE,)")
    assert at.session_state["seen"] == [1, 1]
    _, kept = at.session_state[LAST_READING_KEY]
    assert len(kept.ledger) == 1
    (error,) = _texts(at.error)
    assert "Cannot read case" in error
    assert "log/stream line 2: not a case ledger entry" in error
    assert "Participants" in _texts(at.subheader)
    assert _texts(at.warning) == [NOT_LIVE_NOTE]


@pytest.mark.spec("SHD-04-005")
def test_a_dropped_stream_keeps_the_last_reading_marked_not_live():
    """No close event: the node is lost, and the reading is kept."""
    at = _follow_page("(Dropping(sse_rows(rows[:2])),)")
    assert at.session_state["seen"] == [1, 2, 2]
    _, kept = at.session_state[LAST_READING_KEY]
    assert len(kept.ledger) == 2
    (error,) = _texts(at.error)
    assert "cannot be reached" in error
    assert "Participants" in _texts(at.subheader)
    assert _texts(at.warning) == [NOT_LIVE_NOTE]


def test_a_follow_refused_before_any_reading_shows_only_why():
    at = _follow_page('((404, json.dumps({"detail": "Case not found."})),)')
    (error,) = _texts(at.error)
    assert "holds no such case" in error
    assert "Participants" not in _texts(at.subheader)
    assert not at.warning
    assert not at.info
    assert LIVE_NOTE not in _texts(at.caption)
    assert LAST_READING_KEY not in at.session_state


def test_a_stream_that_closes_before_any_entry_says_so():
    at = _follow_page("(CLOSE,)")
    assert not at.error
    assert _texts(at.warning) == [NO_ENTRY_NOTE]
    assert "Participants" not in _texts(at.subheader)


def test_a_quiet_case_beats_the_heartbeat_while_it_waits():
    """The heartbeat runs at each keepalive and each quiet reconnect."""
    at = _follow_page(
        "(Quiet(sse_rows(rows[:1]) + ': keepalive\\n\\n'),"
        " sse_rows(rows[1:2]) + CLOSE)"
    )
    assert at.session_state["seen"] == [1, 2]
    assert at.session_state[HEARTBEAT_KEY] == 2
    assert _texts(at.warning) == [NOT_LIVE_NOTE]


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
    (error,) = _texts(at.error)
    assert "holds no such case" in error
    assert "Participants" in _texts(at.subheader)
    assert _texts(at.warning) == [NOT_LIVE_NOTE]


@pytest.mark.spec("SHD-04-005")
def test_a_rerun_keeps_its_standing_while_the_follow_replays_the_case():
    """The replay of entries already shown never steps the standing back."""
    at = _follow_page("(sse_rows(rows) + CLOSE,)")
    assert at.session_state["seen"] == [1, 2, 3]
    at.run()
    assert not at.exception
    assert at.session_state["follows"] == 2
    assert at.session_state["seen"] == [1, 2, 3, 3, 3, 3]
    assert _texts(at.warning) == [NOT_LIVE_NOTE]
