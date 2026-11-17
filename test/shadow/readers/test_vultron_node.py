"""The live Vultron case reader over a running node's case ledger (#6530).

It satisfies ``CaseReader``; against a node holding a demo case it returns
every ledger entry the node holds, in log-index order, each citing itself;
it sends only one GET of the ledger list endpoint; and every way the read
can fail raises one domain error naming the node and the case.

Spec: SHD-04-001, SHD-04-002, SHD-04-003, SHD-04-004, SHD-01-002,
CRD-01-001, CRD-01-003, CRD-01-004, CRD-02-001, CRD-02-004.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test.support.act_clock import ACT_AT
from test.support.case_owner import CASE_OWNER_ID
from test.support.case_reader import projected_history
from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driving.fastapi.deps import get_trigger_dl
from vultron.adapters.driving.fastapi.routers import demo_triggers
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.case_reader import CaseReader
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.errors import VultronError, VultronNodeCaseReadError
from vultron.shadow.readers import (
    VultronNodeCaseReader,
    vultron_ledger,
    vultron_node,
)
from vultron.shadow.readers.ledger_reading import NO_ENTRY, ledger_reading
from vultron.shadow.readers.vultron_node import path_segment
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_RECORDING = RECORDINGS_DIR / "rv" / "case-actor.jsonl"
_NODE = "http://node.test/api/v2"
_ACTOR = "case-actor"
_CASE = "urn:uuid:case-1"
_LOG_PATH = "/api/v2/actors/case-actor/demo/cases/case-1/log"


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _ndjson(rows: list[dict[str, Any]] | list[str]) -> str:
    return "\n".join(
        row if isinstance(row, str) else json.dumps(row) for row in rows
    )


def _entry_row(case_id: str, log_index: int) -> dict[str, Any]:
    entry = make(
        CaseLedgerEntry,
        case_id=case_id,
        log_index=log_index,
        log_object_id=f"{case_id}/objects/{log_index}",
        semantic_type=f"test_event_{log_index}",
        received_at=ACT_AT,
        published=ACT_AT,
    )
    return entry.model_dump(mode="json", by_alias=True, exclude_none=True)


class _Recorder:
    """A transport that records every request and answers with *answer*."""

    def __init__(self, answer: Callable[[httpx.Request], httpx.Response]):
        self.requests: list[httpx.Request] = []
        self._answer = answer

    def transport(self) -> httpx.MockTransport:
        def handle(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return self._answer(request)

        return httpx.MockTransport(handle)


def _answering(status: int = 200, body: str = "", **kwargs: Any) -> _Recorder:
    return _Recorder(lambda _r: httpx.Response(status, text=body, **kwargs))


def _reader(recorder: _Recorder) -> VultronNodeCaseReader:
    return VultronNodeCaseReader(_NODE, _ACTOR, transport=recorder.transport())


def _forwarding(client: TestClient) -> _Recorder:
    """A recorder that sends each request on to a node app in-process."""

    def forward(request: httpx.Request) -> httpx.Response:
        answer = client.request(
            request.method,
            request.url.raw_path.decode(),
            headers=dict(request.headers),
        )
        return httpx.Response(
            answer.status_code,
            headers=answer.headers,
            content=answer.content,
        )

    return _Recorder(forward)


@pytest.fixture
def node_dl() -> Iterator[SqliteDataLayer]:
    actor = make(as_Service, name="Case Actor")
    reset_datalayer(actor.id_)
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    store.clear_all()
    store.create(actor)
    yield store
    store.close()
    reset_datalayer(actor.id_)


def _node_app(dl: SqliteDataLayer | None) -> TestClient:
    """A node app; with *dl*, one serving the demo ledger endpoints."""
    app = FastAPI()
    if dl is not None:
        app.include_router(demo_triggers.router, prefix="/api/v2")
        app.dependency_overrides[get_trigger_dl] = lambda: dl
    return TestClient(app)


@pytest.fixture
def demo_case(node_dl: SqliteDataLayer) -> str:
    """The rv recording's case and ledger, held by the node."""
    rows = _rows(_RECORDING)
    case_id = str(rows[0]["caseId"])
    node_dl.create(
        make(
            as_VulnerabilityCase,
            id_=case_id,
            attributed_to=CASE_OWNER_ID,
            name="RV-DEMO",
        )
    )
    for row in reversed(rows):  # stored out of order, served in order
        node_dl.save(CaseLedgerEntry.model_validate(row))
    return case_id


@pytest.mark.spec("CRD-01-001")
def test_the_live_reader_satisfies_the_port():
    assert isinstance(VultronNodeCaseReader(_NODE, _ACTOR), CaseReader)


def test_both_vultron_readers_build_through_the_one_shared_function():
    assert vultron_ledger.ledger_reading is ledger_reading
    assert vultron_node.ledger_reading is ledger_reading


@pytest.mark.spec("SHD-04-003")
@pytest.mark.spec("CRD-01-003")
@pytest.mark.spec("CRD-01-004")
@pytest.mark.parametrize("short", [False, True], ids=["full-id", "short-id"])
def test_a_demo_case_reads_back_every_entry_in_log_index_order(
    node_dl, demo_case, short
):
    recorder = _forwarding(_node_app(node_dl))
    case_id = demo_case.removeprefix("urn:uuid:") if short else demo_case
    reading = _reader(recorder).read_case(case_id)

    expected = [CaseLedgerEntry.model_validate(r) for r in _rows(_RECORDING)]
    assert list(reading.ledger) == expected
    assert [e.log_index for e in reading.ledger] == sorted(
        e.log_index for e in expected
    )
    assert [(c.entry_id, c.source_record) for c in reading.citations] == [
        (e.id_, e.id_) for e in expected
    ]
    projected_history(reading)  # the projection accepts the ledger


@pytest.mark.spec("CRD-02-001")
@pytest.mark.spec("CRD-02-004")
def test_a_reading_has_nothing_untranslated_inferred_or_unobservable(
    node_dl, demo_case
):
    reader = _reader(_forwarding(_node_app(node_dl)))
    reading = reader.read_case(demo_case)
    assert reading.inferences == ()
    assert reading.untranslated == ()
    assert reading.unobservable == reader.unobservable == ()


@pytest.mark.spec("SHD-04-001")
@pytest.mark.spec("SHD-01-002")
def test_the_reader_sends_only_one_get_of_the_ledger_list(node_dl, demo_case):
    recorder = _forwarding(_node_app(node_dl))
    _reader(recorder).read_case(demo_case)
    (request,) = recorder.requests
    assert request.method == "GET"
    assert request.url.host == "node.test"
    segment = demo_case.removeprefix("urn:uuid:")
    assert request.url.path == (
        f"/api/v2/actors/case-actor/demo/cases/{segment}/log"
    )
    assert request.url.params["format"] == "ndjson"
    assert request.content == b""


def test_a_full_actor_id_is_sent_as_its_short_segment():
    recorder = _answering(body=_ndjson([_entry_row(_CASE, 0)]))
    VultronNodeCaseReader(
        _NODE + "/",
        "http://case-actor:7999/api/v2/actors/case-actor/",
        transport=recorder.transport(),
    ).read_case(_CASE)
    assert recorder.requests[0].url.path == _LOG_PATH


@pytest.mark.parametrize(
    ("case_id", "segment"),
    [("a b%2F..", "a%20b%252F.."), ("x?y=1#z", "x"), ("x%3Fy", "x%253Fy")],
)
def test_a_case_id_cannot_add_a_path_segment_or_query(case_id, segment):
    recorder = _answering(404, json.dumps({"detail": "Case not found."}))
    with pytest.raises(VultronNodeCaseReadError):
        _reader(recorder).read_case(case_id)
    (request,) = recorder.requests
    assert request.url.raw_path.decode() == (
        f"/api/v2/actors/case-actor/demo/cases/{segment}/log?format=ndjson"
    )


@pytest.mark.parametrize(
    "case_id", ["", "   ", "..", "x/..", "x/./", "urn:uuid:"]
)
def test_a_case_id_that_names_no_case_is_refused_unsent(case_id):
    recorder = _answering()
    with pytest.raises(VultronNodeCaseReadError, match="names no case"):
        _reader(recorder).read_case(case_id)
    assert recorder.requests == []


def test_an_actor_id_that_names_no_actor_is_refused_at_construction():
    with pytest.raises(ValueError, match="names no case or actor"):
        VultronNodeCaseReader(_NODE, "/")


def test_path_segment_takes_the_last_segment_of_any_id_form():
    assert path_segment("case-actor") == "case-actor"
    assert path_segment("urn:uuid:abc") == "abc"
    assert path_segment("https://n.test/api/v2/actors/vendor") == "vendor"


def _assert_names_node_and_case(exc: VultronNodeCaseReadError) -> None:
    assert isinstance(exc, VultronError)
    assert exc.node_url == _NODE
    assert exc.case_id == _CASE
    assert _NODE in str(exc)
    assert _CASE in str(exc)


@pytest.mark.spec("SHD-04-002")
def test_an_unreachable_node_raises_the_domain_error():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(VultronNodeCaseReadError) as caught:
        _reader(_Recorder(refuse)).read_case(_CASE)
    _assert_names_node_and_case(caught.value)
    assert "cannot be reached (ConnectError)" in str(caught.value)


@pytest.mark.spec("SHD-04-002")
def test_a_node_that_does_not_answer_in_time_raises_the_domain_error():
    def stall(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(VultronNodeCaseReadError) as caught:
        _reader(_Recorder(stall)).read_case(_CASE)
    _assert_names_node_and_case(caught.value)
    assert "did not answer in time" in str(caught.value)


@pytest.mark.spec("SHD-04-002")
def test_a_node_not_serving_the_endpoint_raises_the_domain_error():
    """A node not in prototype run mode has no demo routes: a bare 404."""
    recorder = _forwarding(_node_app(None))
    with pytest.raises(VultronNodeCaseReadError) as caught:
        _reader(recorder).read_case(_CASE)
    _assert_names_node_and_case(caught.value)
    assert "prototype run mode" in str(caught.value)


@pytest.mark.spec("SHD-04-002")
def test_a_node_with_no_such_case_raises_the_domain_error(node_dl):
    recorder = _forwarding(_node_app(node_dl))
    with pytest.raises(VultronNodeCaseReadError) as caught:
        _reader(recorder).read_case(_CASE)
    _assert_names_node_and_case(caught.value)
    assert "holds no such case" in str(caught.value)


def test_a_404_with_a_body_that_is_not_json_reads_as_no_endpoint():
    with pytest.raises(VultronNodeCaseReadError, match="prototype run mode"):
        _reader(_answering(404, "<html>")).read_case(_CASE)


@pytest.mark.parametrize("status", [302, 500, 503])
def test_any_other_answer_raises_the_domain_error_with_its_status(status):
    recorder = _answering(status, headers={"Location": "http://elsewhere/"})
    with pytest.raises(VultronNodeCaseReadError) as caught:
        _reader(recorder).read_case(_CASE)
    _assert_names_node_and_case(caught.value)
    assert f"HTTP {status}" in str(caught.value)
    assert len(recorder.requests) == 1  # a redirect is not followed


@pytest.mark.spec("SHD-04-004")
def test_a_row_that_is_not_a_ledger_entry_refuses_the_reading_whole():
    body = _ndjson([_entry_row(_CASE, 0), {"type": "CaseLedgerEntry"}])
    with pytest.raises(VultronNodeCaseReadError) as caught:
        _reader(_answering(body=body)).read_case(_CASE)
    _assert_names_node_and_case(caught.value)
    (violation,) = caught.value.violations
    assert f"{_LOG_PATH} line 2: not a case ledger entry" in violation.message


@pytest.mark.spec("SHD-04-004")
def test_every_bad_row_is_named_in_line_order():
    body = _ndjson(["not json", _entry_row(_CASE, 0), "[1]", {"x": 1}])
    with pytest.raises(VultronNodeCaseReadError) as caught:
        _reader(_answering(body=body)).read_case(_CASE)
    lines = [v.message for v in caught.value.violations]
    assert [line.split(":")[0] for line in lines] == [
        f"{_LOG_PATH} line 1",
        f"{_LOG_PATH} line 3",
        f"{_LOG_PATH} line 4",
    ]


def test_entries_out_of_log_index_order_are_refused():
    body = _ndjson([_entry_row(_CASE, 1), _entry_row(_CASE, 0)])
    with pytest.raises(VultronNodeCaseReadError, match="log-index order"):
        _reader(_answering(body=body)).read_case(_CASE)


def test_a_case_with_no_entry_is_refused_rather_than_shown_empty(
    node_dl,
):
    node_dl.create(
        make(as_VulnerabilityCase, id_=_CASE, attributed_to=CASE_OWNER_ID)
    )
    recorder = _forwarding(_node_app(node_dl))
    with pytest.raises(VultronNodeCaseReadError) as caught:
        _reader(recorder).read_case(_CASE)
    assert [v.message for v in caught.value.violations] == [NO_ENTRY]
