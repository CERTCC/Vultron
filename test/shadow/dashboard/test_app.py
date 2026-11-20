"""The case shadow tool's app script, run headless with Streamlit's
``AppTest``: a source it cannot use stops the page with why, and the
ledger dir's files are offered as cases.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from test.shadow.dashboard._support import TIMEOUT, texts
from vultron.config import clear_config_cache, config_override
from vultron.config.shadow import ShadowConfig
from vultron.shadow.dashboard.app import APP_PATH, ledger_suggestions
from vultron.shadow.readers import CaseSource


def test_a_connector_that_is_not_installed_stops_the_page_with_why():
    with config_override(VULTRON_SHADOW__CONNECTOR="no-such-connector"):
        at = AppTest.from_file(str(APP_PATH), default_timeout=TIMEOUT).run()
        at.sidebar.radio[0].set_value(CaseSource.OUTSIDE).run()
    assert not at.exception
    (error,) = texts(at.error)
    assert "'no-such-connector'" in error
    assert not at.selectbox and not at.text_input
    # The menu stays, so the analyst can pick another source.
    assert at.sidebar.radio[0].value == CaseSource.OUTSIDE


def test_a_setting_that_does_not_load_stops_the_page_with_why(monkeypatch):
    """A blank connector fails the config load itself, inside the page."""
    monkeypatch.setenv("VULTRON_SHADOW__CONNECTOR", "")
    clear_config_cache()
    try:
        at = AppTest.from_file(str(APP_PATH), default_timeout=TIMEOUT).run()
    finally:
        monkeypatch.delenv("VULTRON_SHADOW__CONNECTOR")
        clear_config_cache()
    assert not at.exception
    (error,) = texts(at.error)
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
