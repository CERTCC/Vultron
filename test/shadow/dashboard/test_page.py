"""The case shadow tool's page, run headless with Streamlit's ``AppTest``.

The real script over a committed recording shows the case's states,
desiderata and open moves (AC-1); the move advice reads band by band, with
its shades, marks, harms and unbanded moves (#6603); a fake reader's
untranslated facts, inferences and unobservable facts are shown beside the
analysis (AC-2); a
read the reader refuses, a ledger with a hole, a reading with no entry and
a setting the reader cannot use each say so on the page.

Spec: SHD-01-002, SHD-01-004, SHD-03-002.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from streamlit.testing.v1 import AppTest

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
from vultron.shadow.dashboard.page import TITLE
from vultron.shadow.dashboard.view import (
    BAND_EMPTY,
    EM_BADGES,
    LEADING_MARK,
    RM_BADGES,
    TOP_MARK,
)

#: Seconds one script run may take; the first run imports the measures.
_TIMEOUT = 60

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
    "Not translated": ["Source record", "Fact", "Why"],
    "Inferred": ["Entry", "Rule", "Caveat"],
    "Not observable": ["Fact", "Why"],
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
    assert any("may have moved on since" in c for c in _texts(at.caption))


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
    assert not at.exception
    (error,) = _texts(at.error)
    assert "'no-such-connector'" in error
    assert not at.selectbox and not at.text_input


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


def test_a_run_through_a_connector_or_with_no_ledger_dir_suggests_none(
    tmp_path,
):
    (tmp_path / "b.jsonl").write_text("")
    assert ledger_suggestions(ShadowConfig()) == []
    assert ledger_suggestions(ShadowConfig(ledger_dir=tmp_path / "gone")) == []
    assert (
        ledger_suggestions(ShadowConfig(connector="x", ledger_dir=tmp_path))
        == []
    )


def test_a_run_through_a_vultron_node_suggests_no_ledger_file(tmp_path):
    """A node's cases are named by case id, not by a file under ledger_dir."""
    (tmp_path / "b.jsonl").write_text("")
    config = ShadowConfig(
        ledger_dir=tmp_path,
        node_url="http://case-actor:7999/api/v2",
        node_actor_id="case-actor",
    )
    assert ledger_suggestions(config) == []
