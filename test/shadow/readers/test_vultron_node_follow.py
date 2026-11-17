"""The live Vultron case reader follows a case over the node's event stream.

Spec: SHD-04-001, SHD-04-003, SHD-04-004 (#6531).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test.shadow.readers.conftest import RECORDING
from test.support.ledger_stream import (
    ACTOR,
    CLOSE,
    NODE,
    Dropping,
    Quiet,
    ScriptedStream,
    ledger_entry_row,
    recording_rows,
    sse_event,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.deps import (
    get_ledger_stream_shutdown,
    get_trigger_dl,
)
from vultron.adapters.driving.fastapi.routers import demo_triggers
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_reading import CaseReading
from vultron.errors import VultronNodeCaseReadError
from vultron.shadow.readers import VultronCaseReader, VultronNodeCaseReader
from vultron.shadow.readers.following import CaseFollower, FollowedReading
from vultron.shadow.readers.vultron_node import DEFAULT_RECONNECTS

_CASE = "urn:uuid:case-1"
_STREAM_PATH = "/api/v2/actors/case-actor/demo/cases/case-1/log/stream"


def _entries(*indices: int) -> str:
    return "".join(sse_event(ledger_entry_row(_CASE, i), i) for i in indices)


def _follow(
    script: ScriptedStream,
    *,
    reconnects: int = DEFAULT_RECONNECTS,
    heartbeat: Callable[[], None] | None = None,
) -> list[FollowedReading]:
    reader = script.reader(reconnects=reconnects)
    return list(reader.follow_case(_CASE, heartbeat=heartbeat))


def _sizes(items: list[FollowedReading]) -> list[int | str]:
    return [
        len(item.ledger) if isinstance(item, CaseReading) else "refused"
        for item in items
    ]


def test_the_live_reader_can_follow_and_the_file_reader_cannot():
    assert isinstance(VultronNodeCaseReader(NODE, ACTOR), CaseFollower)
    assert not isinstance(VultronCaseReader(), CaseFollower)


@pytest.mark.spec("SHD-04-003")
def test_three_streamed_entries_yield_three_whole_readings_in_order():
    """AC-1: one, two and three entries, each whole, in log-index order."""
    items = _follow(ScriptedStream(_entries(0, 1, 2) + CLOSE))
    assert _sizes(items) == [1, 2, 3]
    for item in items:
        assert isinstance(item, CaseReading)
        assert [e.log_index for e in item.ledger] == list(
            range(len(item.ledger))
        )
        assert [(c.entry_id, c.source_record) for c in item.citations] == [
            (e.id_, e.id_) for e in item.ledger
        ]


@pytest.mark.spec("SHD-04-004")
def test_an_invalid_entry_is_refused_by_name_never_left_out():
    """AC-2: the reading after a bad entry is a refusal naming it."""
    body = (
        _entries(0)
        + sse_event({"type": "CaseLedgerEntry"}, 1)
        + _entries(2)
        + CLOSE
    )
    items = _follow(ScriptedStream(body))
    assert _sizes(items) == [1, "refused", "refused"]
    for refusal in items[1:]:
        assert isinstance(refusal, VultronNodeCaseReadError)
        assert refusal.node_url == NODE
        assert refusal.case_id == _CASE
        (violation,) = refusal.violations
        assert violation.message.startswith(
            f"{_STREAM_PATH} line 2: not a case ledger entry"
        )


@pytest.mark.spec("SHD-04-004")
def test_an_entry_that_is_not_json_is_refused_by_name():
    items = _follow(
        ScriptedStream(_entries(0) + sse_event("not json", 1) + CLOSE)
    )
    refusal = items[1]
    assert isinstance(refusal, VultronNodeCaseReadError)
    (violation,) = refusal.violations
    assert violation.message.startswith(f"{_STREAM_PATH} line 2: Parse error")


def test_entries_out_of_log_index_order_are_refused():
    items = _follow(ScriptedStream(_entries(1, 0) + CLOSE))
    assert isinstance(items[-1], VultronNodeCaseReadError)
    assert "log-index order" in str(items[-1].violations)


def test_a_stream_of_another_case_is_refused():
    body = sse_event(ledger_entry_row("urn:uuid:case-2", 0), 0) + CLOSE
    (refusal,) = _follow(ScriptedStream(body))
    assert isinstance(refusal, VultronNodeCaseReadError)
    assert [v.message for v in refusal.violations] == [
        "the node answered with the ledger of case urn:uuid:case-2"
    ]


@pytest.mark.spec("SHD-04-001")
@pytest.mark.spec("SHD-01-002")
def test_following_sends_only_gets_of_the_stream_endpoint():
    script = ScriptedStream(Dropping(_entries(0)), _entries(1) + CLOSE)
    _follow(script)
    assert len(script.requests) == 2
    for request in script.requests:
        assert request.method == "GET"
        assert request.url.host == "node.test"
        assert request.url.path == _STREAM_PATH
        assert request.url.query == b""
        assert request.headers["accept"] == "text/event-stream"
        assert request.content == b""


@pytest.mark.spec("SHD-04-001")
def test_a_dropped_stream_resumes_after_the_last_event_received():
    """AC-3: the reconnect sends Last-Event-ID, so nothing is replayed."""
    script = ScriptedStream(Dropping(_entries(0, 1)), _entries(2) + CLOSE)
    items = _follow(script)
    assert _sizes(items) == [1, 2, 3]
    first, second = script.requests
    assert "last-event-id" not in first.headers
    assert second.headers["last-event-id"] == "1"


def test_a_stream_that_ends_unclosed_is_reconnected():
    script = ScriptedStream(_entries(0), _entries(1) + CLOSE)
    assert _sizes(_follow(script)) == [1, 2]
    assert script.requests[1].headers["last-event-id"] == "0"


def test_a_lost_stream_before_any_entry_reconnects_from_the_start():
    script = ScriptedStream(Dropping(""), _entries(0) + CLOSE)
    assert _sizes(_follow(script)) == [1]
    assert "last-event-id" not in script.requests[1].headers


@pytest.mark.spec("SHD-04-002")
def test_a_node_lost_for_good_ends_the_follow_with_why():
    beats: list[None] = []
    script = ScriptedStream(Dropping(_entries(0)))  # then every connect fails
    items = _follow(script, reconnects=2, heartbeat=lambda: beats.append(None))
    assert _sizes(items) == [1, "refused"]
    refusal = items[-1]
    assert isinstance(refusal, VultronNodeCaseReadError)
    assert refusal.node_url == NODE and refusal.case_id == _CASE
    assert "cannot be reached (ConnectError)" in str(refusal.violations)
    # The first connection, then two reconnect tries.
    assert len(script.requests) == 3
    assert len(beats) == 2


def test_a_node_that_drops_every_connection_unanswered_ends_the_follow():
    script = ScriptedStream("", "", "")
    items = _follow(script, reconnects=2)
    (refusal,) = items
    assert isinstance(refusal, VultronNodeCaseReadError)
    assert "without closing it" in str(refusal.violations)
    assert len(script.requests) == 3


def test_an_entry_resets_the_count_of_lost_connections():
    script = ScriptedStream(
        Dropping(""),
        Dropping(_entries(0)),
        _entries(1) + CLOSE,
    )
    # Two losses with one try allowed: the entry between them reset it.
    assert _sizes(_follow(script, reconnects=1)) == [1, 2]


def test_a_quiet_stream_is_reconnected_without_ending_the_follow():
    beats: list[None] = []
    script = ScriptedStream(
        Quiet(_entries(0)),
        Quiet(""),
        Quiet(""),
        _entries(1) + CLOSE,
    )
    items = _follow(script, reconnects=0, heartbeat=lambda: beats.append(None))
    assert _sizes(items) == [1, 2]
    assert len(beats) == 3
    assert script.requests[-1].headers["last-event-id"] == "0"


@pytest.mark.spec("SHD-04-002")
def test_a_node_that_does_not_answer_in_time_is_a_lost_connection():
    script = ScriptedStream(httpx.ReadTimeout("slow"))
    (refusal,) = _follow(script, reconnects=0)
    assert isinstance(refusal, VultronNodeCaseReadError)
    assert "did not answer in time" in str(refusal.violations)


@pytest.mark.spec("SHD-04-002")
@pytest.mark.parametrize(
    ("answer", "problem"),
    [
        ((404, json.dumps({"detail": "Case not found."})), "no such case"),
        ((404, "<html>"), "prototype run mode"),
        ((500, ""), "HTTP 500"),
    ],
)
def test_an_answer_that_is_no_stream_ends_the_follow_untried(answer, problem):
    script = ScriptedStream(answer)
    (refusal,) = _follow(script)
    assert isinstance(refusal, VultronNodeCaseReadError)
    assert problem in str(refusal.violations)
    assert len(script.requests) == 1


def test_a_case_id_that_names_no_case_is_refused_unsent():
    script = ScriptedStream()
    reader = script.reader()
    (refusal,) = list(reader.follow_case(".."))
    assert isinstance(refusal, VultronNodeCaseReadError)
    assert "names no case" in str(refusal.violations)
    assert script.requests == []


def test_comments_and_other_events_are_not_entries():
    body = ": keep-alive\n\nevent: ping\ndata: x\n\n" + _entries(0) + CLOSE
    assert _sizes(_follow(ScriptedStream(body))) == [1]


def test_closing_the_follow_closes_the_stream():
    closed: list[bool] = []

    class _Open(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            yield _entries(0, 1).encode()

        def close(self) -> None:
            closed.append(True)

    follow = ScriptedStream(_Open()).reader().follow_case(_CASE)
    assert isinstance(next(follow), CaseReading)
    follow.close()
    assert closed == [True]


def test_negative_reconnects_or_delay_are_refused():
    with pytest.raises(ValueError, match="must not be negative"):
        VultronNodeCaseReader(NODE, ACTOR, reconnects=-1)
    with pytest.raises(ValueError, match="must not be negative"):
        VultronNodeCaseReader(NODE, ACTOR, retry_delay=-1)


def _closing_node_app(dl: SqliteDataLayer) -> TestClient:
    """A node app whose ledger stream replays the store, then closes."""
    app = FastAPI()
    app.include_router(demo_triggers.router, prefix="/api/v2")
    shutdown = threading.Event()
    shutdown.set()
    app.dependency_overrides[get_trigger_dl] = lambda: dl
    app.dependency_overrides[get_ledger_stream_shutdown] = lambda: shutdown
    return TestClient(app)


def _forwarded(client: TestClient, request: httpx.Request) -> httpx.Response:
    """The node app's answer to *request*, as *client* receives it."""
    return client.request(
        request.method,
        request.url.raw_path.decode(),
        headers=dict(request.headers),
    )


def _forwarding_transport(client: TestClient) -> httpx.MockTransport:
    def forward(request: httpx.Request) -> httpx.Response:
        answer = _forwarded(client, request)
        return httpx.Response(
            answer.status_code, headers=answer.headers, content=answer.content
        )

    return httpx.MockTransport(forward)


@pytest.mark.spec("SHD-04-003")
@pytest.mark.parametrize("short", [False, True], ids=["full-id", "short-id"])
def test_a_demo_case_followed_on_a_node_grows_to_its_whole_ledger(
    node_dl,
    demo_case,
    short,
):
    transport = _forwarding_transport(_closing_node_app(node_dl))
    reader = VultronNodeCaseReader(NODE, ACTOR, transport=transport)
    case_id = demo_case.removeprefix("urn:uuid:") if short else demo_case
    items = list(reader.follow_case(case_id))

    expected = [
        CaseLedgerEntry.model_validate(r) for r in recording_rows(RECORDING)
    ]
    assert _sizes(items) == list(range(1, len(expected) + 1))
    last = items[-1]
    assert isinstance(last, CaseReading)
    assert list(last.ledger) == expected
    assert last == reader.read_case(case_id)


def test_a_keepalive_comment_beats_the_heartbeat_and_is_no_entry():
    beats: list[None] = []
    body = _entries(0) + ": keepalive\n\n: keepalive\n\n" + _entries(1) + CLOSE
    items = _follow(ScriptedStream(body), heartbeat=lambda: beats.append(None))
    assert _sizes(items) == [1, 2]
    assert len(beats) == 2


def test_only_a_try_that_is_made_is_logged_as_one(caplog):
    with caplog.at_level("WARNING"):
        _follow(ScriptedStream(Dropping("")), reconnects=1)
    messages = [r.getMessage() for r in caplog.records]
    assert sum("reconnecting, try 1 of 1" in m for m in messages) == 1
    assert not any("try 2" in m for m in messages)
    assert any(m.startswith("Stopped following case") for m in messages)


@pytest.mark.spec("SHD-04-001")
def test_a_real_node_resumes_a_dropped_stream_after_the_last_entry(
    node_dl, demo_case
):
    """The node itself answers Last-Event-ID with only the later entries."""
    client = _closing_node_app(node_dl)
    requests: list[httpx.Request] = []
    replayed: list[int] = []

    def forward(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        answer = _forwarded(client, request)
        events = [e for e in answer.text.split("\n\n") if e.startswith("id:")]
        replayed.append(len(events))
        headers = {"Content-Type": "text/event-stream"}
        if len(requests) == 1:  # drop after the first two entries
            body = "".join(f"{e}\n\n" for e in events[:2])
            return httpx.Response(200, headers=headers, stream=Dropping(body))
        return httpx.Response(200, headers=headers, content=answer.content)

    reader = VultronNodeCaseReader(
        NODE, ACTOR, transport=httpx.MockTransport(forward), retry_delay=0
    )
    items = list(reader.follow_case(demo_case))

    total = len(recording_rows(RECORDING))
    assert _sizes(items) == list(range(1, total + 1))
    assert items[-1] == reader.read_case(demo_case)
    assert requests[1].headers["last-event-id"] == "1"
    assert replayed[:2] == [total, total - 2]


def test_a_keepalive_resets_the_count_of_connections_lost_in_a_row():
    """Drops apart in time, each after a keepalive, do not add up."""
    script = ScriptedStream(
        Dropping(": keepalive\n\n"),
        Dropping(": keepalive\n\n"),
        _entries(0) + CLOSE,
    )
    assert _sizes(_follow(script, reconnects=1)) == [1]


def test_an_event_without_an_id_keeps_the_resume_point():
    """A reconnected stream's id-less event does not clear Last-Event-ID."""
    script = ScriptedStream(
        Dropping(_entries(0)),
        Dropping("event: ping\ndata: x\n\n"),
        _entries(1) + CLOSE,
    )
    assert _sizes(_follow(script)) == [1, 2]
    assert [r.headers.get("last-event-id") for r in script.requests] == [
        None,
        "0",
        "0",
    ]


def test_a_quiet_reconnect_is_logged_at_debug(caplog):
    script = ScriptedStream(Quiet(_entries(0)), _entries(1) + CLOSE)
    with caplog.at_level("DEBUG", logger="vultron.shadow.readers"):
        assert _sizes(_follow(script)) == [1, 2]
    assert any(
        r.levelname == "DEBUG" and "went quiet; reconnecting" in r.getMessage()
        for r in caplog.records
    )
