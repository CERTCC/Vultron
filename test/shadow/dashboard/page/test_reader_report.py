"""The page's reader report, run headless with Streamlit's ``AppTest``: a
fake reader's untranslated facts, inferences and unobservable facts
are shown beside the analysis (AC-2).

Spec: SHD-01-004.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from test.shadow.dashboard._support import TIMEOUT, texts
from test.shadow.dashboard.page._support import FAKE_PAGE, page_table
from vultron.shadow.dashboard.page import END_UNCONFIRMED_NOTE


@pytest.mark.spec("SHD-01-004")
def test_the_untranslated_facts_are_shown_beside_the_analysis():
    """AC-2: a fake reader's untranslated facts are on the page."""
    at = AppTest.from_string(FAKE_PAGE, default_timeout=TIMEOUT).run()
    at.text_input[0].input("urn:uuid:case-1").run()
    assert not at.exception
    headings = texts(at.subheader)
    assert headings.index("Participants") < headings.index("Not translated")
    untranslated = page_table(at, "Not translated")
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
    assert len(page_table(at, "Inferred")) == 3
    assert page_table(at, "Not observable")["Fact"].tolist() == [
        "Fix deployed (D)"
    ]
    # Nothing proves the fake case's last entry is its last.
    assert END_UNCONFIRMED_NOTE in texts(at.caption)
