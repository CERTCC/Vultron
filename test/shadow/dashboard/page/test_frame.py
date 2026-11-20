"""The page's frame, run headless with Streamlit's ``AppTest``: it asks
for a case, reads it only through the reader's ``read_case`` and shows
every reason the reader refuses it.

Spec: SHD-01-002.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from test.shadow.dashboard._support import TIMEOUT, texts
from test.shadow.dashboard.page._support import FAKE_PAGE
from vultron.config import config_override
from vultron.shadow.dashboard.app import APP_PATH
from vultron.shadow.dashboard.page import TITLE

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


def test_the_page_asks_for_a_case_before_reading_any(recordings_app):
    at = recordings_app.run()
    assert not at.exception
    assert texts(at.title) == [TITLE]
    assert "Enter a case to see where it stands." in texts(at.info)
    assert "rv/case-actor.jsonl" in at.selectbox[0].options


def test_a_blank_case_is_no_case():
    at = AppTest.from_string(FAKE_PAGE, default_timeout=TIMEOUT).run()
    at.text_input[0].input("   ").run()
    assert not at.exception
    assert "Enter a case to see where it stands." in texts(at.info)


@pytest.mark.spec("SHD-01-002")
def test_the_page_reads_the_case_only_through_read_case():
    at = AppTest.from_string(_SPY_PAGE, default_timeout=TIMEOUT).run()
    at.text_input[0].input("urn:uuid:case-1").run()
    assert not at.exception
    assert at.session_state["read"] == ["urn:uuid:case-1"]
    assert "touched" not in at.session_state


def test_a_case_the_reader_refuses_shows_every_reason(tmp_path):
    (tmp_path / "bad.jsonl").write_text("not json\n{}\n")
    with config_override(VULTRON_SHADOW__LEDGER_DIR=str(tmp_path)):
        at = AppTest.from_file(str(APP_PATH), default_timeout=TIMEOUT).run()
        at.selectbox[0].select("bad.jsonl").run()
    assert not at.exception
    (error,) = texts(at.error)
    assert "Cannot read a case from bad.jsonl (2 violation(s))" in error
    assert "Participants" not in texts(at.subheader)
