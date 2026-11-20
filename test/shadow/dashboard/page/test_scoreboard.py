"""The page's scoreboard, run headless with Streamlit's ``AppTest``: the
real script over a committed recording shows the case's states,
desiderata and open moves (AC-1), each state on its machine's map
(#6674), and a reading with no entry or a ledger with a hole says so.

Spec: CRD-02-005.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from test.shadow.dashboard._support import (
    RV,
    TIMEOUT,
    recording_analysis,
    texts,
)
from test.shadow.dashboard.page._support import page_table
from vultron.config import config_override
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.measure.advice import Band
from vultron.measure.baselines import scope_desiderata
from vultron.shadow.dashboard import minimap
from vultron.shadow.dashboard.app import APP_PATH
from vultron.shadow.dashboard.view import (
    BAND_EMPTY,
    DESIDERATA_NOTE,
    EM_BADGES,
    RM_BADGES,
)

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


def test_a_recorded_case_shows_its_states_desiderata_and_moves(
    recordings_app,
):
    """AC-1: entering a case shows its states, desiderata and open moves."""
    at = recordings_app.run()
    at.selectbox[0].select("rcvv-embargo/case-actor.jsonl").run()
    assert not at.exception
    metrics = texts(at.metric)
    assert metrics[0] in EM_BADGES.values()
    assert len(metrics) == 4
    participants = page_table(at, "Participants")
    assert "Vendor" in participants["Participant"].tolist()
    assert set(participants["Report"]) <= set(RM_BADGES.values())
    desiderata = page_table(at, "Desiderata")
    assert len(desiderata) == len(scope_desiderata())
    assert {"Vendor", "Vendor2"} <= set(desiderata.columns)
    # The pair desideratum move advice leaves out is named, not just absent.
    assert DESIDERATA_NOTE in texts(at.caption)
    moves = page_table(at, "Harm-free")
    assert len(moves) > 0
    assert set(moves["Machine"]) <= {"RM", "CS", "EM"}
    assert set(page_table(at, "Moves with no band")["Machine"]) <= {
        "RM",
        "CS",
        "EM",
    }
    # No move of this recording trades off or is unhelpful: each band says
    # so, the unhelpful one inside its closed group.
    assert BAND_EMPTY[Band.TRADE_OFF] in texts(at.caption)
    (unhelpful,) = [
        e for e in at.expander if str(e.label).startswith("Unhelpful")
    ]
    assert texts(unhelpful.caption) == [BAND_EMPTY[Band.UNHELPFUL]]
    # The recording ends on the CASE_MANAGER's closure: nothing follows.
    assert not any("moved on" in c for c in texts(at.caption))


def test_a_case_with_no_scored_vendor_names_no_left_out_desideratum(
    recordings_app,
):
    """rcv-reject's only vendor refuses its invitation: the table is empty,
    so there is nothing to say about what it leaves out."""
    at = recordings_app.run()
    at.selectbox[0].select("rcv-reject/case-actor.jsonl").run()
    assert not at.exception
    captions = texts(at.caption)
    assert "No vendor has a case-state history to score yet." in captions
    assert DESIDERATA_NOTE not in captions


def test_each_state_is_shown_on_its_machines_map(recordings_app):
    """#6674 AC-1: the case's EM and public state, then each participant's
    RM and fix path in its own tab, each on its map with its state marked."""
    case = "rcvv-embargo/case-actor.jsonl"
    at = recordings_app.run()
    at.selectbox[0].select(case).run()
    assert not at.exception
    analysis = recording_analysis(RECORDINGS_DIR / case)
    standing = analysis.standing
    assert standing is not None and standing.case is not None
    participants = minimap.participant_minimaps(
        standing.participants, analysis.actor_names
    )
    expected = list(minimap.case_minimaps(standing.case))
    for p in participants:
        expected.extend(m for m in (p.rm, p.vfd) if m is not None)
    charts = at.get("graphviz_chart")
    assert [c.proto.spec for c in charts] == [m.dot for m in expected]
    assert [t.label for t in at.tabs] == [p.tab for p in participants]
    captions = texts(at.caption)
    assert all(m.caption in captions for m in expected)
    assert any(p.vfd is None for p in participants)
    assert minimap.NO_FIX_PATH in captions


_NO_PARTICIPANTS_PAGE = """
from vultron.shadow.dashboard.page.scoreboard import _show_participant_minimaps

_show_participant_minimaps([], {})
"""


#: One participant whose name, from the case's source, is Markdown.
_MARKDOWN_NAME_PAGE = """
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.measure.sequences import (
    UnprojectableParticipant,
    UnprojectableReason,
)
from vultron.measure.standing import CaseStanding, ParticipantStanding
from vultron.shadow.dashboard.page.scoreboard import _show_participant_minimaps

VENDOR = "https://vendor.example/actors/vendor"
_show_participant_minimaps(
    [
        ParticipantStanding(
            participant=VENDOR,
            rm=RM.RECEIVED,
            case=CaseStanding(em=EM.NONE, pxa=CS_pxa.pxa),
            unscored=UnprojectableParticipant(
                participant=VENDOR,
                reason=UnprojectableReason.NO_CASE_STATE_EVENTS,
                detail="it has no event of its own",
            ),
        )
    ],
    {VENDOR: "![x](https://host.example/p.png)"},
)
"""


def test_a_participants_tab_shows_its_name_as_literal_text():
    """A name from the case's source reaches its tab escaped, so the page
    never renders it as Markdown (an image would fetch an outside URL)."""
    at = AppTest.from_string(
        _MARKDOWN_NAME_PAGE, default_timeout=TIMEOUT
    ).run()
    assert not at.exception
    assert [t.label for t in at.tabs] == [
        minimap.markdown_literal("![x](https://host.example/p.png)")
    ]


def test_a_standing_with_no_participant_draws_no_participant_tabs():
    at = AppTest.from_string(
        _NO_PARTICIPANTS_PAGE, default_timeout=TIMEOUT
    ).run()
    assert not at.exception
    assert not at.tabs
    assert not at.get("graphviz_chart")


#: The fake case, read from a source that cannot observe attacks or a
#: fix being ready.
_UNSEEN_PAGE = """
from test.support.case_reader import FAKE_CASE, FakeCaseReader, fake_case_records
from vultron.core.models.case_reading import UnobservableFact
from vultron.core.states.cs_invariants import CSEvent
from vultron.shadow.dashboard.page import render


class Unseen(FakeCaseReader):
    unobservable = (
        UnobservableFact(
            fact="Attacks (A), fix ready (F)",
            why="No field records them.",
            events=frozenset({CSEvent.A, CSEvent.F}),
        ),
    )


render(Unseen({FAKE_CASE: fake_case_records()}))
"""


@pytest.mark.spec("CRD-02-005")
def test_an_unobservable_event_reads_as_unknown_on_the_page():
    """The top row's badge and the public-state map both read an event the
    source cannot observe as unknown."""
    at = AppTest.from_string(_UNSEEN_PAGE, default_timeout=TIMEOUT).run()
    at.text_input[0].input("urn:uuid:case-1").run()
    assert not at.exception
    assert texts(at.metric)[3] == "❔ Attacks Observed unknown"
    pxa = at.get("graphviz_chart")[1]
    assert "dashed" in pxa.proto.spec
    assert any(
        c.endswith("❔ Attacks Observed unknown") for c in texts(at.caption)
    )


def test_a_reading_with_no_entry_shows_its_report_and_no_standing():
    at = AppTest.from_string(_EMPTY_PAGE, default_timeout=TIMEOUT).run()
    at.text_input[0].input("any").run()
    assert not at.exception
    assert any("translated no ledger entry" in w for w in texts(at.warning))
    assert "Participants" not in texts(at.subheader)
    assert "Case narrative" not in texts(at.subheader)
    assert page_table(at, "Not translated")["Source record"].tolist() == [
        "rec-9"
    ]


def test_a_ledger_with_a_hole_shows_the_hole_not_a_standing(tmp_path):
    rows = RV.read_text().splitlines()
    (tmp_path / "holed.jsonl").write_text(
        "\n".join(rows[:2] + rows[3:]) + "\n"
    )
    with config_override(VULTRON_SHADOW__LEDGER_DIR=str(tmp_path)):
        at = AppTest.from_file(str(APP_PATH), default_timeout=TIMEOUT).run()
        at.selectbox[0].select("holed.jsonl").run()
    assert not at.exception
    assert any("has a hole" in e for e in texts(at.error))
    assert "- Missing log indices: [2]" in texts(at.markdown)
    assert "Participants" not in texts(at.subheader)
    assert "Not translated" in texts(at.subheader)
