"""The page's case narrative, run headless with Streamlit's ``AppTest``:
one line per ledger entry, each with its hindsight mark (#6670,
#6672).
"""

from __future__ import annotations

import re

from test.shadow.dashboard._support import texts
from test.shadow.dashboard.page._support import (
    BACKGROUND,
    page_frame,
    page_table,
)
from test.support.ledger_stream import recording_rows
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.measure.advice import BAND_COLOUR_MAPS
from vultron.shadow.dashboard import view
from vultron.shadow.dashboard.page import HINDSIGHT_NOTE, NARRATIVE_NOTE


def test_a_recorded_case_shows_its_narrative_one_line_per_entry(
    recordings_app,
):
    """#6670 AC-1, AC-2: one line per ledger entry, in log-index order,
    naming who did what and which states it changed."""
    at = recordings_app.run()
    at.selectbox[0].select("rcvv-embargo/case-actor.jsonl").run()
    assert not at.exception
    assert "Case narrative" in texts(at.subheader)
    assert NARRATIVE_NOTE in texts(at.caption)
    narrative = page_table(at, "Case narrative")
    entries = recording_rows(
        RECORDINGS_DIR / "rcvv-embargo" / "case-actor.jsonl"
    )
    assert narrative["#"].tolist() == list(range(len(entries)))
    assert narrative["Activity"].tolist()[0] == "Case Actor created the case"
    changes = " ".join(narrative["State changes"])
    assert "EM: " in changes and "VFD: " in changes and "PXA: " in changes


def test_each_narrative_line_carries_its_hindsight_mark_in_its_shade(
    recordings_app,
):
    """#6672 AC-1: one mark per line, each an icon from the mark table,
    with the note saying what it graded; a best, good or sub-optimal mark's
    cell alone takes a shade from its band's legend."""
    at = recordings_app.run()
    at.selectbox[0].select("rcvv-embargo/case-actor.jsonl").run()
    assert not at.exception
    assert HINDSIGHT_NOTE in texts(at.caption)
    narrative = page_table(at, "Case narrative")
    marks = narrative[view.HINDSIGHT_COLUMN].tolist()
    labels = {f"{icon} {mark}" for mark, icon in view.HINDSIGHT_ICONS.items()}
    assert set(marks) <= labels
    assert "⭐ best" in marks and "💬 not a move" in marks
    notes = narrative[view.HINDSIGHT_NOTE_COLUMN].tolist()
    assert all(
        note for mark, note in zip(marks, notes, strict=True) if "💬" in mark
    )
    styles = page_frame(at, "Case narrative").proto.arrow_data.styler.styles
    # Only the mark's column is styled, and only on a shaded mark's row.
    assert set(re.findall(r"_col(\d+)", styles)) == {"1"}
    assert {int(r) for r in re.findall(r"row(\d+)_col1", styles)} == {
        row
        for row, mark in enumerate(marks)
        if mark.split()[0] in ("⭐", "👍", "⚠️")
    }
    shaded = BACKGROUND.findall(styles)
    legend_shades = {
        s.background
        for colour_map in BAND_COLOUR_MAPS.values()
        for deepest in range(1, 6)
        for s in view.band_legend_shades(colour_map, deepest)
    }
    assert set(shaded) <= legend_shades
