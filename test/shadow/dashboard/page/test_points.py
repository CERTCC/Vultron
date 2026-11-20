"""The page's point picker, run headless with Streamlit's ``AppTest``:
the scoreboard at a picked narrative line is the case just after it
(#6671).
"""

from __future__ import annotations

from itertools import pairwise

import pytest
from streamlit.testing.v1 import AppTest

from test.shadow.dashboard._support import (
    RCVV,
    TIMEOUT,
    recording_analysis,
    texts,
)
from test.shadow.dashboard.page._support import (
    BACKGROUND,
    FAKE_PAGE,
    page_over_file,
    page_table,
    point_picker,
    scoreboard,
)
from test.support.ledger_stream import recording_rows
from vultron.measure.advice import case_advice
from vultron.measure.baselines import scope_desiderata
from vultron.measure.standing import DesideratumStatus
from vultron.shadow.analysis import point_analysis
from vultron.shadow.dashboard import minimap, view
from vultron.shadow.dashboard.page import END_UNCONFIRMED_NOTE, POINT_KEY
from vultron.shadow.dashboard.view import (
    DESIDERATA_NOTE,
    DESIDERATUM_BADGES,
    LATEST_POINT,
    LEGEND_BETTER,
)


def _cut_page(tmp_path, recording, count: int) -> AppTest:
    """The page over a copy of *recording* cut after *count* entries."""
    rows = recording.read_text().splitlines()[:count]
    (tmp_path / "cut.jsonl").write_text("\n".join(rows) + "\n")
    at = page_over_file(tmp_path, "cut.jsonl")
    assert not at.exception
    return at


@pytest.mark.parametrize("log_index", [3, 30])
def test_picking_a_narrative_line_shows_the_case_just_after_it(
    recordings_app, tmp_path, log_index
):
    """#6671 AC-1: the states, desiderata and move bands at line N are the
    ones a reading of entries up to N alone shows; the narrative stays
    whole."""
    at = recordings_app.run()
    at.selectbox[0].select("rcvv-embargo/case-actor.jsonl").run()
    now = scoreboard(at)
    picker = point_picker(at)
    assert picker.value == LATEST_POINT
    picker.select(log_index).run()
    assert not at.exception
    assert point_picker(at).value == log_index
    assert at.session_state[POINT_KEY] == (
        "rcvv-embargo/case-actor.jsonl",
        log_index,
    )
    assert any(f"just after entry #{log_index}" in i for i in texts(at.info))
    at_point = scoreboard(at)
    assert at_point != now
    assert at_point == scoreboard(_cut_page(tmp_path, RCVV, log_index + 1))
    entries = recording_rows(RCVV)
    assert len(page_table(at, "Case narrative")) == len(entries)


def _vendor_status(board: dict[str, object], events: str) -> str:
    """The first vendor's status for the desideratum *events* names."""
    table = board["Desideratum"]
    assert isinstance(table, dict)
    return str(table["Vendor"][table["Events"].index(events)])


def test_the_full_desiderata_table_follows_the_picked_point(recordings_app):
    """#6669 with #6671: at a picked point the desiderata table still holds
    every desideratum move advice sums, under its caption, and an embargo
    desideratum reads as it stood then: ExOwn ≺ P is open just after entry
    #30 of this recording and broken at its end."""
    log_index = 30
    at = recordings_app.run()
    at.selectbox[0].select("rcvv-embargo/case-actor.jsonl").run()
    now = scoreboard(at)
    point_picker(at).select(log_index).run()
    assert not at.exception
    at_point = scoreboard(at)
    table = at_point["Desideratum"]
    assert isinstance(table, dict)
    assert len(table["Desideratum"]) == len(scope_desiderata())
    captions = at_point["captions"]
    assert isinstance(captions, list)
    assert DESIDERATA_NOTE in captions
    open_, broken = (
        DESIDERATUM_BADGES[DesideratumStatus.OPEN],
        DESIDERATUM_BADGES[DesideratumStatus.BROKEN],
    )
    assert _vendor_status(at_point, "ExOwn ≺ P") == open_
    assert _vendor_status(now, "ExOwn ≺ P") == broken


def _legend_cells(at: AppTest) -> dict[str, list[str]]:
    """Each shaded band's legend cells, by the band's title."""
    markdowns = texts(at.markdown)
    return {
        title.strip("*"): BACKGROUND.findall(legend)
        for title, legend in pairwise(markdowns)
        if LEGEND_BETTER in legend
    }


def test_the_state_maps_and_band_legends_follow_the_picked_point(
    recordings_app,
):
    """#6674: the EM and public-state maps, each participant's RM and fix
    path maps, and #6673's band legends are drawn from the picked point's
    standing, not from where the case stands now.

    At entry #57 of this recording the harm-free band has two layers and
    the trade-off band has moves, where at its end the harm-free band has
    one layer and the trade-off band none.
    """
    log_index = 57
    at = recordings_app.run()
    at.selectbox[0].select("rcvv-embargo/case-actor.jsonl").run()
    now = scoreboard(at)
    point_picker(at).select(log_index).run()
    assert not at.exception
    analysis = point_analysis(
        recording_analysis(),
        log_index,
    )
    standing = analysis.standing
    assert standing is not None and standing.case is not None
    participants = minimap.participant_minimaps(
        standing.participants, analysis.actor_names
    )
    expected = list(minimap.case_minimaps(standing.case))
    for p in participants:
        expected.extend(m for m in (p.rm, p.vfd) if m is not None)
    at_point = scoreboard(at)
    assert at_point["maps"] == [m.dot for m in expected]
    assert at_point["maps"] != now["maps"]
    assert at_point["tabs"] == [p.tab for p in participants]
    legends = {
        band.title: [s.background for s in band.legend]
        for band in view.band_views(
            case_advice(standing), analysis.actor_names
        )
        if band.rows and band.shaded
    }
    assert set(legends) == {"Harm-free", "Trade-off"}
    assert _legend_cells(at) == legends
    point_picker(at).select(LATEST_POINT).run()
    assert _legend_cells(at) != legends


def test_picking_now_shows_where_the_case_stands_again(recordings_app):
    at = recordings_app.run()
    at.selectbox[0].select("rcvv-embargo/case-actor.jsonl").run()
    now = scoreboard(at)
    point_picker(at).select(3).run()
    assert scoreboard(at) != now
    point_picker(at).select(LATEST_POINT).run()
    assert not at.exception
    assert POINT_KEY not in at.session_state
    assert scoreboard(at) == now
    assert not any("just after entry" in i for i in texts(at.info))


def test_a_past_point_does_not_hedge_that_the_case_may_have_moved_on():
    """The fake case's end is unproven: its last entry hedges, and an
    earlier point, after which the case is known to move on, does not."""
    at = AppTest.from_string(FAKE_PAGE, default_timeout=TIMEOUT).run()
    at.text_input[0].input("urn:uuid:case-1").run()
    assert END_UNCONFIRMED_NOTE in texts(at.caption)
    picker = point_picker(at)
    first, *_, last = picker.options[1:]
    picker.select(last).run()
    assert not at.exception
    assert END_UNCONFIRMED_NOTE in texts(at.caption)
    point_picker(at).select(first).run()
    assert not at.exception
    assert END_UNCONFIRMED_NOTE not in texts(at.caption)


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
    now = scoreboard(at)
    at.session_state[POINT_KEY] = kept
    at.run()
    assert not at.exception
    assert point_picker(at).value == LATEST_POINT
    assert scoreboard(at) == now
    assert at.session_state[POINT_KEY] == kept
