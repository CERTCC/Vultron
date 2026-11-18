"""The case shadow tool's source menu, run headless with ``AppTest`` (#6642).

The page opens on the recorded demo cases and offers VINCE and a running
Vultron node from a menu in its sidebar.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from streamlit.testing.v1 import AppTest

from test.support.case_reader import (
    FAKE_CASE,
    FakeCaseReader,
    fake_case_records,
)
from vultron.config import clear_config_cache, config_override
from vultron.config.app import AppConfig
from vultron.config.shadow import ShadowConfig
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.shadow.dashboard.app import APP_PATH, NO_SOURCE_NOTE
from vultron.shadow.dashboard.page import CASE_KEY, LAST_READING_KEY
from vultron.shadow.dashboard.source_menu import (
    NODE_ACTOR_KEY,
    NODE_URL_KEY,
    SOURCE_LABELS,
    VINCE_NOT_SET_UP,
    source_label,
)
from vultron.shadow.readers import CaseSource, selection

#: Seconds one script run may take; the first run imports the measures.
_TIMEOUT = 60

#: The settings the Compose service runs with when the shell sets none.
_COMPOSE = {"VULTRON_SHADOW__LEDGER_DIR": str(RECORDINGS_DIR)}

_VINCE = {
    "VULTRON_VINCE__BASE_URL": "https://vince.test/vince/comm/api",
    "VULTRON_VINCE__API_TOKEN": "test-only-credential",
}


def _texts(elements) -> list[str]:
    return [str(element.value) for element in elements]


def _app(**env: str) -> Iterator[AppTest]:
    with config_override(**{**_COMPOSE, **env}):
        yield AppTest.from_file(str(APP_PATH), default_timeout=_TIMEOUT)


@pytest.fixture(autouse=True)
def _no_source_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Start with no source setting, whatever the host's environment holds."""
    for name in (
        *_VINCE,
        "VULTRON_SHADOW__CONNECTOR",
        "VULTRON_SHADOW__NODE_URL",
        "VULTRON_SHADOW__NODE_ACTOR_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    yield
    # The environment is restored after this; the next read reloads it.
    clear_config_cache()


@pytest.fixture
def app() -> Iterator[AppTest]:
    yield from _app()


@pytest.fixture
def vince_app() -> Iterator[AppTest]:
    yield from _app(**_VINCE)


def _menu(at: AppTest):
    (menu,) = at.sidebar.radio
    return menu


def _choose(at: AppTest, source: CaseSource) -> AppTest:
    _menu(at).set_value(source).run()
    assert not at.exception
    return at


def test_the_page_opens_on_the_recorded_demo_cases(app):
    """AC-1: no source setting; the recordings are offered and read."""
    at = app.run()
    assert not at.exception
    assert _menu(at).value == CaseSource.RECORDINGS
    (case_box,) = at.selectbox
    assert "rv/case-actor.jsonl" in case_box.options
    case_box.select("rv/case-actor.jsonl").run()
    assert not at.exception
    assert "Participants" in _texts(at.subheader)


def test_the_menu_lists_the_recordings_vince_and_a_running_node(vince_app):
    """AC-2: the three sources, by name."""
    at = vince_app.run()
    assert _menu(at).options == [
        SOURCE_LABELS[CaseSource.RECORDINGS],
        SOURCE_LABELS[CaseSource.OUTSIDE],
        SOURCE_LABELS[CaseSource.NODE],
    ]


def test_choosing_a_node_reads_through_the_live_reader(app, monkeypatch):
    """AC-2: the source chosen is the reader the page uses, no restart."""
    built: list[tuple[str, str]] = []

    def live_reader(url: str, actor_id: str) -> FakeCaseReader:
        built.append((url, actor_id))
        return FakeCaseReader({FAKE_CASE: fake_case_records()})

    monkeypatch.setattr(selection, "VultronNodeCaseReader", live_reader)
    at = _choose(app.run(), CaseSource.NODE)
    # The node URL is unique to this test, so no cached reader answers.
    at.text_input(key=NODE_URL_KEY).input("http://menu-test:7999/api/v2")
    at.text_input(key=NODE_ACTOR_KEY).input("case-actor").run()
    assert not at.exception
    assert not at.selectbox, "a node offers no recorded case"
    at.text_input(key=CASE_KEY).input(FAKE_CASE).run()
    assert not at.exception
    assert built == [("http://menu-test:7999/api/v2", "case-actor")]
    assert "Participants" in _texts(at.subheader)


def test_switching_sources_drops_the_case_and_its_kept_reading(app):
    """AC-2: a case read from one source is never shown under another."""
    at = app.run()
    at.selectbox[0].select("rv/case-actor.jsonl").run()
    assert "Participants" in _texts(at.subheader)
    at.session_state[LAST_READING_KEY] = ("rv/case-actor.jsonl", None)
    _choose(at, CaseSource.NODE)
    assert LAST_READING_KEY not in at.session_state
    assert "Participants" not in _texts(at.subheader)
    _choose(at, CaseSource.RECORDINGS)
    assert at.selectbox[0].value is None
    assert "Enter a case to see where it stands." in _texts(at.info)


@pytest.mark.spec("SHD-02-003")
def test_vince_cannot_be_chosen_without_its_url_and_credential(app):
    """AC-3: chosen unset, VINCE reads nothing and says what to set."""
    at = app.run()
    assert _menu(at).options[1].endswith("(not set up)")
    _choose(at, CaseSource.OUTSIDE)
    assert VINCE_NOT_SET_UP in _texts(at.sidebar.info)
    assert NO_SOURCE_NOTE in _texts(at.info)
    assert not at.selectbox and not at.text_input


@pytest.mark.spec("SHD-02-003")
def test_vince_set_in_the_environment_can_be_chosen(vince_app):
    at = _choose(vince_app.run(), CaseSource.OUTSIDE)
    assert _menu(at).options[1] == SOURCE_LABELS[CaseSource.OUTSIDE]
    assert not at.error
    (case_box,) = at.text_input
    assert case_box.key == CASE_KEY


@pytest.mark.spec("SHD-02-003")
def test_no_source_has_a_field_for_a_credential(vince_app):
    """AC-3: the only fields are the case and the node's address."""
    at = vince_app.run()
    for source in CaseSource:
        _choose(at, source)
        keys = {box.key for box in at.text_input}
        assert keys <= {CASE_KEY, NODE_URL_KEY, NODE_ACTOR_KEY}
        for box in at.text_input:
            assert "token" not in box.label.lower()
            assert "credential" not in box.label.lower()
            assert box.proto.type != box.proto.PASSWORD


def test_the_node_fields_are_prefilled_from_the_settings():
    """AC-4: the shadow: settings fill the node's address."""
    for at in _app(
        VULTRON_SHADOW__NODE_URL="http://case-actor:7999/api/v2",
        VULTRON_SHADOW__NODE_ACTOR_ID="case-actor",
    ):
        _choose(at.run(), CaseSource.NODE)
        assert (
            at.text_input(key=NODE_URL_KEY).value
            == "http://case-actor:7999/api/v2"
        )
        assert at.text_input(key=NODE_ACTOR_KEY).value == "case-actor"
        assert at.text_input(key=CASE_KEY)


def test_settings_that_name_a_node_still_open_on_the_recordings():
    for at in _app(
        VULTRON_SHADOW__NODE_URL="http://case-actor:7999/api/v2",
        VULTRON_SHADOW__NODE_ACTOR_ID="case-actor",
    ):
        at.run()
        assert _menu(at).value == CaseSource.RECORDINGS


@pytest.mark.parametrize(
    ("url", "actor_id", "reason"),
    [
        ("http://user:secret@case-actor:7999/api", "case-actor", "API root"),
        ("case-actor:7999", "case-actor", "http:// or https://"),
        ("http://case-actor:7999/api/v2", "", "enter both"),
        (
            "http://case-actor:7999/api/v2",
            "acct?token=secret",
            "names no actor",
        ),
    ],
    ids=["userinfo", "no-scheme", "no-actor", "bad-actor"],
)
def test_a_typed_node_the_settings_refuse_is_refused_unread(
    app, monkeypatch, url, actor_id, reason
):
    """AC-4: refused with a message, and no reader is built to send."""

    def no_reader(*_args: object) -> None:
        raise AssertionError("a reader was built for a refused node")

    monkeypatch.setattr(selection, "VultronNodeCaseReader", no_reader)
    at = _choose(app.run(), CaseSource.NODE)
    at.text_input(key=NODE_URL_KEY).input(url)
    at.text_input(key=NODE_ACTOR_KEY).input(actor_id).run()
    assert not at.exception
    (error,) = _texts(at.sidebar.error)
    assert reason in error
    assert "secret" not in error
    assert NO_SOURCE_NOTE in _texts(at.info)
    assert CASE_KEY not in {box.key for box in at.text_input}


def test_switching_nodes_drops_the_reading_kept_for_the_first(
    app, monkeypatch
):
    """AC-2: one node's reading is never shown as another node's."""
    monkeypatch.setattr(
        selection,
        "VultronNodeCaseReader",
        lambda _url, _actor: FakeCaseReader({FAKE_CASE: fake_case_records()}),
    )
    at = _choose(app.run(), CaseSource.NODE)
    at.text_input(key=NODE_URL_KEY).input("http://node-one:7999/api/v2")
    at.text_input(key=NODE_ACTOR_KEY).input("case-actor").run()
    at.text_input(key=CASE_KEY).input(FAKE_CASE).run()
    assert "Participants" in _texts(at.subheader)
    at.session_state[LAST_READING_KEY] = (FAKE_CASE, None)
    at.text_input(key=NODE_URL_KEY).input("http://node-two:7999/api/v2").run()
    assert not at.exception
    assert LAST_READING_KEY not in at.session_state
    assert at.text_input(key=CASE_KEY).value == ""
    assert "Participants" not in _texts(at.subheader)


def test_another_connector_is_offered_by_its_name():
    config = AppConfig().model_copy(
        update={"shadow": ShadowConfig(connector="acme")}
    )
    assert source_label(CaseSource.OUTSIDE, config) == "Outside system (acme)"
