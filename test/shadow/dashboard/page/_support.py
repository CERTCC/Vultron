"""What the page tests share: the fake case's page script, the page run
over one ledger file, the tables a page draws and the shades in their
styles, what its scoreboard shows and its point picker."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from streamlit.testing.v1 import AppTest

from test.shadow.dashboard._support import TIMEOUT, texts
from vultron.config import config_override
from vultron.shadow.dashboard.app import APP_PATH
from vultron.shadow.dashboard.page import END_UNCONFIRMED_NOTE

if TYPE_CHECKING:
    from pathlib import Path

#: The page over the fake case reader's one case.
FAKE_PAGE = """
from test.support.case_reader import FAKE_CASE, FakeCaseReader, fake_case_records
from vultron.shadow.dashboard.page import render

render(FakeCaseReader({FAKE_CASE: fake_case_records()}))
"""


def page_over_file(ledger_dir: Path, name: str) -> AppTest:
    """The page over the ledgers in *ledger_dir*, run with the file *name*
    picked."""
    with config_override(VULTRON_SHADOW__LEDGER_DIR=str(ledger_dir)):
        at = AppTest.from_file(str(APP_PATH), default_timeout=TIMEOUT).run()
        at.selectbox[0].select(name).run()
    return at


#: Each table's columns, which tell the tables apart.
COLUMNS = {
    "Participants": [
        "Participant",
        "Roles",
        "Joined",
        "Report",
        "Fix path",
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
        "Hindsight",
        "Time",
        "Committed",
        "Actor",
        "Activity",
        "Object",
        "State changes",
        "Hindsight note",
    ],
    "Not translated": ["Source record", "Fact", "Why"],
    "Inferred": ["Entry", "Rule", "Caveat"],
    "Not observable": ["Fact", "Why", "Reads as unknown"],
}

#: A background colour in a cell's or a legend's style.
BACKGROUND = re.compile(r"background-color: (#[0-9a-f]{6})")

#: The tables a scoreboard draws, which follow the picked point.
SCOREBOARD = ("Participants", "Harm-free", "Trade-off", "Moves with no band")


def page_frame(at: AppTest, heading: str):
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
        if columns == COLUMNS.get(heading):
            return frame
    raise AssertionError(f"no {heading!r} table on the page")


def page_table(at: AppTest, heading: str):
    """The table drawn under *heading*, as a data frame."""
    return page_frame(at, heading).value


def scoreboard(at: AppTest) -> dict[str, object]:
    """What the page's scoreboard shows: its metrics, its captions, its
    state maps and participant tabs, its Markdown (map titles, band titles
    and legend strips) and each of its tables, ``None`` for one it draws
    empty."""
    shown: dict[str, object] = {
        "metrics": texts(at.metric),
        # A past point does not hedge on the case's end, as a cut file must.
        "captions": [
            c for c in texts(at.caption) if c != END_UNCONFIRMED_NOTE
        ],
        "maps": [chart.proto.spec for chart in at.get("graphviz_chart")],
        "tabs": [tab.label for tab in at.tabs],
        "markdown": texts(at.markdown),
    }
    for frame in at.dataframe:
        columns = frame.value.columns.tolist()
        heading = next(
            (h for h, c in COLUMNS.items() if c == columns), columns[0]
        )
        if heading in SCOREBOARD or heading == "Desideratum":
            shown[heading] = frame.value.to_dict("list")
    return shown


def point_picker(at: AppTest):
    """The page's point picker."""
    (picker,) = [box for box in at.selectbox if box.label.startswith("Show")]
    return picker
