#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""The per-route contract of every trigger verb, asserted once over the registry.

Each trigger route used to carry its own copy of three checks: it answers
``202``, it resolves the addressed actor's store through the ``get_trigger_dl``
seam, and it queues the outbox flush as a background task.  With every route
body reduced to one ``run_trigger(...)`` call (ADR-0110), those are properties
of the shared path, so they are asserted here once per registry row
(TRIG-12-004) instead of once per route file:

- **Exact response keys (TRIG-12-002).**  ``set(response.json())`` equals the
  row's ``result_type`` field set, and a key whose value is ``None`` is still
  emitted as ``null`` — FastAPI's ``response_model_exclude_*`` and ``by_alias``
  defaults are untouched.  A route that adds, drops or filters a key fails.
- **Addressed store (TRIG-06-001, TRIG-06-002).**  The dispatcher is handed the
  row's request type carrying the path's ``actor_id`` and the very store the
  ``get_trigger_dl`` override returned.
- **Flush after dispatch (TRIG-07-001, TRIG-01-004).**  Exactly one outbox
  flush per trigger run is queued for the addressed actor's store, after the
  dispatcher has returned, and the response is ``202`` (TRIG-01-002).
- **Full case id (ADR-0032, BT-25-007).**  A case-scoped request reaches the
  dispatcher naming a stored case by its full id, whether the client sent the
  full id or the short id, and a reference to no stored case is refused before
  the dispatcher with the structured 404 a trigger raises for an unknown case.
  The canned dispatcher refuses any case-scoped request that does not name a
  stored case's full id, so every contract test below also checks this.

The dispatcher here is a hand-written ``TriggerDispatcher`` that returns a
canned instance of the row's result type with every optional key ``None`` —
not ``Mock(spec=...)`` (``vultron/core/ports/AGENTS.md``) — because this file
is about the route layer's serialization and wiring.  The domain assertions
per verb (state transition, addressing, error body) stay in the per-router
suites, which run the real registry-backed dispatcher.

Bodies are the smallest valid request per verb, keyed by verb so a new row
must add one; the result catalogue is keyed by result type for the same
reason.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from test.adapters.driving.fastapi.test_trigger_registry_routes import (
    trigger_routes,
)
from test.support.objects import make
from test.support.trigger_routes import (
    build_prototype_app,
)
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driving.fastapi.deps import (
    get_trigger_dispatcher,
    get_trigger_dl,
    outbox_store,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.use_case_result import (
    ActivityResult,
    CaseResult,
    NoteResult,
    OfferResult,
    RoleOfferResult,
    StatusResult,
    SyncLogEntryResult,
    TriggerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.trigger_dispatcher import TriggerDispatcher
from vultron.core.states.cs import CS_vf
from vultron.core.use_cases.triggers._helpers import resolve_case
from vultron.core.use_cases.triggers.request_bodies import CaseTriggerRequest
from vultron.core.use_cases.triggers.requests import (
    AddOnBehalfStatusTriggerRequest,
    ResultT_co,
    TriggerRequest,
    result_type_of,
)
from vultron.errors import VultronNotFoundError
from vultron.trigger_registry import TriggerEntry, entries
from vultron.wire.as2.vocab.base.objects.actors import as_Service

_ACTOR = "urn:uuid:3833a9b0-0000-4000-8000-000000000001"
_CASE = "https://example.org/cases/c1"
#: A case a client names by its short id (surrogate key, the id's last
#: segment).  A trigger body's ``case_id`` is a ``UriString``, so only a short
#: id with a scheme-like prefix gets past the body; a bare ``c1`` is a 422.
_SHORT_NAMED_CASE = "https://example.org/cases/VU:42"
_CASE_SHORT_ID = "VU:42"
_OTHER = "https://example.org/actors/other"
_FUTURE = (datetime.now(UTC) + timedelta(days=30)).isoformat()

#: The route runs through ``run_trigger``, so the flush it schedules is the
#: helper's ``outbox_handler`` reference.
_FLUSH = "vultron.adapters.driving.fastapi.trigger_runner.outbox_handler"

#: The smallest body each verb's request model accepts.  Keyed by verb; the
#: coverage test below fails when a registry row has no entry here.
_BODIES: dict[str, dict[str, Any]] = {
    "ack-report": {"offer_id": "urn:uuid:offer"},
    "validate-report": {"offer_id": "urn:uuid:offer"},
    "invalidate-report": {"offer_id": "urn:uuid:offer"},
    "reject-report": {"offer_id": "urn:uuid:offer", "note": "Out of scope."},
    "submit-report": {
        "report_name": "Report",
        "report_content": "Content",
        "recipient_id": _OTHER,
    },
    "engage-case": {"case_id": _CASE},
    "defer-case": {"case_id": _CASE},
    "leave-case": {"case_id": _CASE},
    "remove-participant": {"case_id": _CASE, "participant_actor_id": _OTHER},
    "reinstate-participant": {
        "case_id": _CASE,
        "participant_actor_id": _OTHER,
    },
    "add-object-to-case": {"case_id": _CASE, "object_id": "urn:uuid:obj"},
    "create-case": {"name": "Case", "content": "Content"},
    "add-report-to-case": {"case_id": _CASE, "report_id": "urn:uuid:report"},
    "propose-embargo": {"case_id": _CASE, "end_time": _FUTURE},
    "accept-embargo": {"case_id": _CASE},
    "reject-embargo": {"case_id": _CASE},
    "propose-embargo-revision": {"case_id": _CASE, "end_time": _FUTURE},
    "terminate-embargo": {"case_id": _CASE},
    "withdraw-embargo": {"case_id": _CASE},
    "suggest-actor-to-case": {"case_id": _CASE, "suggested_actor_id": _OTHER},
    "accept-case-invite": {"invite_id": "urn:uuid:invite"},
    "accept-full-case-invite": {"invite_id": "urn:uuid:invite"},
    "tentative-reject-full-case-invite": {"invite_id": "urn:uuid:invite"},
    "reject-full-case-invite": {"invite_id": "urn:uuid:invite"},
    "reject-case-invite": {"invite_id": "urn:uuid:invite"},
    "invite-actor-to-case": {"case_id": _CASE, "invitee_id": _OTHER},
    "accept-actor-recommendation": {
        "cp_offer_id": "urn:uuid:cp-offer",
        "case_actor_id": _OTHER,
    },
    "reject-actor-recommendation": {
        "cp_offer_id": "urn:uuid:cp-offer",
        "case_actor_id": _OTHER,
    },
    "offer-case-participant-role": {
        "case_id": _CASE,
        "target_actor_id": _OTHER,
        "role": "vendor",
    },
    "offer-case-ownership-transfer": {
        "case_id": _CASE,
        "transferee_id": _OTHER,
    },
    "accept-case-ownership-transfer": {"offer_id": "urn:uuid:offer"},
    "reject-case-ownership-transfer": {"offer_id": "urn:uuid:offer"},
    "withdraw-case-ownership-transfer": {"offer_id": "urn:uuid:offer"},
    "add-note-to-case": {
        "case_id": _CASE,
        "note_name": "Note",
        "note_content": "Content",
    },
    "notify-fix-ready": {"case_id": _CASE},
    "notify-fix-deployed": {"case_id": _CASE},
    "notify-published": {"case_id": _CASE},
    "add-on-behalf-status": {
        "case_id": _CASE,
        "target_actor_id": _OTHER,
        "vf_state": "Vf",
    },
    "sync-log-entry": {
        "case_id": _CASE,
        "object_id": _CASE,
    },
    "set-stub-summary": {
        "case_id": _CASE,
        "stub_summary": "Test stub summary",
    },
}

#: Verbs whose route runs more than one trigger: ``notify-fix-ready`` is the
#: two-hop VF ratchet (vf→Vf→VF), so it dispatches and flushes twice.
_RUNS_PER_VERB: dict[str, int] = {"notify-fix-ready": 2}

#: One canned instance per result type, every optional key left ``None`` so
#: the response proves ``null`` keys are emitted (TRIG-12-002).  Keyed by
#: type; the coverage test below fails when a row's result type is missing.
_CANNED: dict[type[TriggerResult], TriggerResult] = {
    ActivityResult: ActivityResult(activity=None, emitting_actor_id=_ACTOR),
    NoteResult: NoteResult(activity=None, emitting_actor_id=_ACTOR, note=None),
    CaseResult: CaseResult(
        activity=None, emitting_actor_id=_ACTOR, case_id=None
    ),
    StatusResult: StatusResult(activity_id=None, status_id=None),
    OfferResult: OfferResult(offer=None),
    RoleOfferResult: RoleOfferResult(
        activity_id="urn:uuid:offer", activity={"type": "Offer"}
    ),
    SyncLogEntryResult: SyncLogEntryResult(
        log_entry_id="urn:uuid:entry",
        entry_hash="0" * 64,
        log_index=0,
        emitting_actor_id=_ACTOR,
    ),
}


_RESULT_TYPES = sorted(_CANNED, key=lambda t: t.__name__)


class _CannedDispatcher:
    """A ``TriggerDispatcher`` that records each call and answers canned.

    It stands in for the trigger use case, so it also holds the edge to its
    promise: a case-scoped request it receives names a case *store* holds, by
    that case's full id (the ``/case_id`` seed, BT-25-007).
    """

    def __init__(self, store: SqliteDataLayer) -> None:
        self._store = store
        self.calls: list[
            tuple[TriggerRequest[Any], CaseOutboxPersistence]
        ] = []

    def trigger(
        self,
        request: TriggerRequest[ResultT_co],
        dl: CaseOutboxPersistence,
    ) -> ResultT_co:
        if isinstance(request, CaseTriggerRequest):
            held = self._store.read(request.case_id)
            assert isinstance(held, VulnerabilityCase), request.case_id
            assert held.id_ == request.case_id
        self.calls.append((request, dl))
        result = _CANNED[result_type_of(type(request))]
        # The canned instance *is* the bound type: ``_CANNED`` is keyed by it.
        return result  # type: ignore[return-value]


def _rows() -> list[TriggerEntry]:
    return list(entries())


def _ids(row: TriggerEntry) -> str:
    return row.verb


@pytest.fixture(scope="module")
def app() -> FastAPI:
    """The prototype app once: construction is slow and the routes are fixed."""
    return build_prototype_app()


@pytest.fixture(scope="module")
def route_paths(app: FastAPI) -> dict[tuple[Any, str], str]:
    document: dict[str, Any] = app.openapi()
    return trigger_routes(document["paths"])


@pytest.fixture
def store():
    """The addressed actor's store: the actor and the case every body names."""
    reset_datalayer(_ACTOR)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
    dl.clear_all()
    dl.create(make(as_Service, id_=_ACTOR, name="Actor"))
    _store_case(dl, _CASE)
    yield dl
    dl.close()
    reset_datalayer(_ACTOR)


@pytest.fixture
def dispatcher(store: SqliteDataLayer) -> _CannedDispatcher:
    return _CannedDispatcher(store)


@pytest.fixture
def client(
    app: FastAPI, store: SqliteDataLayer, dispatcher: _CannedDispatcher
):
    app.dependency_overrides[get_trigger_dl] = lambda: store
    app.dependency_overrides[get_trigger_dispatcher] = lambda: dispatcher
    yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def flush():
    with patch(_FLUSH, new_callable=AsyncMock) as mocked:
        yield mocked


def _post(
    client: TestClient,
    route_paths,
    row: TriggerEntry,
    case_id: str | None = None,
):
    """POST the row's minimal body, naming *case_id* in place of ``_CASE``."""
    path = route_paths[(row.exposure, row.verb)].replace("{actor_id}", _ACTOR)
    body = _BODIES[row.verb]
    if case_id is not None:
        body = {k: case_id if v == _CASE else v for k, v in body.items()}
    return client.post(path, json=body)


def _store_case(store: SqliteDataLayer, case_id: str) -> None:
    store.create(
        make(VulnerabilityCase, id_=case_id, name="Case", attributed_to=_ACTOR)
    )


def _case_rows() -> list[TriggerEntry]:
    """The rows whose request names a case (``CaseTriggerRequest``)."""
    return [
        r for r in _rows() if issubclass(r.request_model, CaseTriggerRequest)
    ]


# ---------------------------------------------------------------------------
# Catalogue coverage: a new row must declare its body and its result shape
# ---------------------------------------------------------------------------


def test_every_registry_verb_has_a_minimal_body() -> None:
    assert set(_BODIES) == {row.verb for row in _rows()}


def test_every_registry_result_type_has_a_canned_instance() -> None:
    assert set(_CANNED) == {row.result_type for row in _rows()}


@pytest.mark.parametrize(
    "result_type", _RESULT_TYPES, ids=[t.__name__ for t in _RESULT_TYPES]
)
def test_canned_instance_is_exactly_its_type(
    result_type: type[TriggerResult],
) -> None:
    """The catalogue cannot hand a subtype where a row names the base."""
    assert type(_CANNED[result_type]) is result_type


# ---------------------------------------------------------------------------
# The contract, per row
# ---------------------------------------------------------------------------


@pytest.mark.spec("TRIG-12-002")
@pytest.mark.spec("TRIG-01-002")
@pytest.mark.parametrize("row", _rows(), ids=_ids)
def test_route_answers_202_with_exactly_the_rows_keys(
    client, route_paths, flush, row: TriggerEntry
) -> None:
    """``set(response.json()) == expected_keys``, nulls included.

    Equality against the canned result's own JSON dump is stricter than the
    key set alone: it also pins that no value was re-shaped on the way out.
    """
    resp = _post(client, route_paths, row)
    assert resp.status_code == 202, resp.text
    body = resp.json()
    expected = _CANNED[row.result_type]
    assert set(body) == set(row.result_type.model_fields)
    assert body == expected.model_dump(mode="json")


@pytest.mark.spec("TRIG-12-002")
@pytest.mark.parametrize(
    "row",
    [
        r
        for r in _rows()
        if any(v is None for v in _CANNED[r.result_type].model_dump().values())
    ],
    ids=_ids,
)
def test_null_valued_keys_are_still_emitted(
    client, route_paths, flush, row: TriggerEntry
) -> None:
    """A key the use case left ``None`` reaches the client as ``null``.

    ``activity`` is ``None`` whenever the BT captured nothing; dropping it
    would silently remove a key clients receive today (TRIG-12-002 rationale).
    """
    body = _post(client, route_paths, row).json()
    null_keys = {
        k
        for k, v in _CANNED[row.result_type].model_dump().items()
        if v is None
    }
    assert null_keys, row.result_type.__name__
    for key in null_keys:
        assert key in body and body[key] is None, (key, body)


@pytest.mark.spec("TRIG-06-001")
@pytest.mark.spec("TRIG-06-002")
@pytest.mark.spec("TRIG-12-004")
@pytest.mark.parametrize("row", _rows(), ids=_ids)
def test_dispatcher_receives_the_rows_request_over_the_addressed_store(
    client, route_paths, flush, dispatcher: _CannedDispatcher, store, row
) -> None:
    """The route builds the row's request from the body plus the path actor and
    hands it, with the ``get_trigger_dl`` store, to the dispatcher."""
    _post(client, route_paths, row)
    runs = _RUNS_PER_VERB.get(row.verb, 1)
    assert len(dispatcher.calls) == runs
    for request, dl in dispatcher.calls:
        assert type(request) is row.request_model
        assert request.actor_id == _ACTOR
        assert dl is store


@pytest.mark.spec("TRIG-07-001")
@pytest.mark.spec("TRIG-01-004")
@pytest.mark.parametrize("row", _rows(), ids=_ids)
def test_flush_is_queued_once_per_run_for_the_addressed_actor(
    client, route_paths, flush: AsyncMock, store, row: TriggerEntry
) -> None:
    """One background flush per trigger run, ``(actor_id, store)``, and no
    third positional (that slot is ``emitter`` — see
    ``test/architecture/test_outbox_handler_emitter_keyword.py``)."""
    _post(client, route_paths, row)
    runs = _RUNS_PER_VERB.get(row.verb, 1)
    assert flush.await_count == runs
    for call in flush.await_args_list:
        assert call.args == (_ACTOR, store)
        assert call.kwargs == {}


@pytest.mark.spec("TRIG-07-001")
@pytest.mark.parametrize("row", _rows(), ids=_ids)
def test_nothing_is_flushed_when_the_dispatcher_raises(
    app, route_paths, store, flush: AsyncMock, row: TriggerEntry
) -> None:
    """A trigger that raised flushes nothing; the error is the structured 404."""

    class _Raising:
        def trigger(self, request, dl):
            raise VultronNotFoundError("Actor", request.actor_id)

    app.dependency_overrides[get_trigger_dl] = lambda: store
    app.dependency_overrides[get_trigger_dispatcher] = _Raising
    try:
        resp = _post(TestClient(app), route_paths, row)
    finally:
        app.dependency_overrides = {}
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "NotFound"
    flush.assert_not_awaited()


@pytest.mark.spec("TRIG-07-001")
@pytest.mark.spec("TRIG-01-004")
def test_two_run_route_flushes_nothing_when_its_second_run_raises(
    app, route_paths, store, flush: AsyncMock
) -> None:
    """``notify-fix-ready`` dispatches twice; if the second hop raises, the
    first hop's queued flush never runs either.

    ``BackgroundTasks`` are attached to the response only when the endpoint
    returns, so an error response carries none — the activity hop 1 queued
    stays in the outbox until the actor's next drain, exactly as it did when
    the route scheduled one flush after both hops.  This pins that the two-call
    body did not change the failure path.
    """

    class _SecondCallRaises:
        def __init__(self) -> None:
            self.calls = 0

        def trigger(self, request, dl):
            self.calls += 1
            if self.calls == 2:
                raise VultronNotFoundError("Case", request.case_id)
            return _CANNED[result_type_of(type(request))]

    dispatcher = _SecondCallRaises()
    app.dependency_overrides[get_trigger_dl] = lambda: store
    app.dependency_overrides[get_trigger_dispatcher] = lambda: dispatcher
    try:
        row = next(r for r in _rows() if r.verb == "notify-fix-ready")
        resp = _post(TestClient(app), route_paths, row)
    finally:
        app.dependency_overrides = {}
    assert dispatcher.calls == 2
    assert resp.status_code == 404
    flush.assert_not_awaited()


# ---------------------------------------------------------------------------
# The case reference: resolved to the full id at the edge (ADR-0032)
# ---------------------------------------------------------------------------


#: The trigger routers that build a case request (#6678 AC-1).  The report
#: routers build none, so they are not listed.
_CASE_ROUTERS = (
    "trigger_case",
    "trigger_embargo",
    "trigger_actor.invitations",
    "trigger_actor.ownership",
    "trigger_actor.recommendations",
    "demo_triggers.actions",
)


@pytest.mark.parametrize("module_name", _CASE_ROUTERS)
def test_every_case_router_serves_a_case_scoped_row(
    route_paths, module_name: str
) -> None:
    """The case rows below reach every router that builds a case request.

    Each router module's own POST routes are matched against the case rows'
    mounted paths, so a router whose case routes all left the registry, or
    stopped building a ``CaseTriggerRequest``, fails here.
    """
    module = importlib.import_module(
        f"vultron.adapters.driving.fastapi.routers.{module_name}"
    )
    own = {
        route.path
        for route in module.router.routes
        if isinstance(route, APIRoute) and "POST" in (route.methods or ())
    }
    case_paths = [route_paths[(r.exposure, r.verb)] for r in _case_rows()]
    assert any(path.endswith(tuple(own)) for path in case_paths), own


@pytest.mark.spec("BT-25-007")
@pytest.mark.parametrize("row", _case_rows(), ids=_ids)
def test_a_short_case_id_reaches_the_dispatcher_as_the_full_id(
    client, route_paths, flush, dispatcher: _CannedDispatcher, store, row
) -> None:
    """A client's short case id is the case's full id in the core request."""
    _store_case(store, _SHORT_NAMED_CASE)
    resp = _post(client, route_paths, row, case_id=_CASE_SHORT_ID)
    assert resp.status_code == 202, resp.text
    assert len(dispatcher.calls) == _RUNS_PER_VERB.get(row.verb, 1)
    for request, _ in dispatcher.calls:
        assert isinstance(request, CaseTriggerRequest)
        assert request.case_id == _SHORT_NAMED_CASE


@pytest.mark.parametrize("row", _case_rows(), ids=_ids)
def test_a_full_case_id_reaches_the_dispatcher_unchanged(
    client, route_paths, flush, dispatcher: _CannedDispatcher, row
) -> None:
    """The edge passes the very request on when it already names the full id."""
    resp = _post(client, route_paths, row)
    assert resp.status_code == 202, resp.text
    assert len(dispatcher.calls) == _RUNS_PER_VERB.get(row.verb, 1)
    for request, _ in dispatcher.calls:
        assert isinstance(request, CaseTriggerRequest)
        assert request.case_id == _CASE


@pytest.mark.parametrize("row", _case_rows(), ids=_ids)
def test_an_unknown_case_is_refused_before_the_dispatcher(
    client,
    route_paths,
    flush: AsyncMock,
    dispatcher: _CannedDispatcher,
    store,
    row,
) -> None:
    """A reference to no stored case gets the trigger's not-found error.

    The body is the one the trigger use case raises for an unknown case
    (``resolve_case``), so moving the refusal to the edge does not change
    what the client gets: ``404`` with ``VultronNotFoundError``'s message for
    the reference as sent.
    """
    unknown = "https://example.org/cases/unknown"
    with pytest.raises(VultronNotFoundError) as raised:
        resolve_case(unknown, store)
    resp = _post(client, route_paths, row, case_id=unknown)
    assert resp.status_code == 404, resp.text
    assert resp.json() == {
        "detail": {
            "status": 404,
            "error": "NotFound",
            "message": str(raised.value),
            "activity_id": None,
        }
    }
    assert str(raised.value) == f"VulnerabilityCase '{unknown}' not found."
    assert dispatcher.calls == []
    flush.assert_not_awaited()


@pytest.mark.parametrize("row", _case_rows(), ids=_ids)
def test_an_unknown_actor_is_refused_before_its_case(
    app, route_paths, flush: AsyncMock, dispatcher: _CannedDispatcher, row
) -> None:
    """An unknown actor's store holds no case, so the actor is what is missing.

    The trigger use case resolves its actor before its case, so the edge's
    refusal names the actor too, not the case the empty store cannot hold.
    """
    stranger = "urn:uuid:3833a9b0-0000-4000-8000-0000000000ff"
    reset_datalayer(stranger)
    empty = SqliteDataLayer("sqlite:///:memory:", actor_id=stranger)
    empty.clear_all()
    app.dependency_overrides[get_trigger_dl] = lambda: empty
    app.dependency_overrides[get_trigger_dispatcher] = lambda: dispatcher
    try:
        path = route_paths[(row.exposure, row.verb)].replace(
            "{actor_id}", stranger
        )
        resp = TestClient(app).post(path, json=_BODIES[row.verb])
    finally:
        app.dependency_overrides = {}
        empty.close()
        reset_datalayer(stranger)
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"]["message"] == f"Actor '{stranger}' not found."
    assert dispatcher.calls == []
    flush.assert_not_awaited()


@pytest.mark.parametrize("row", _case_rows(), ids=_ids)
def test_an_ambiguous_short_case_id_is_refused_as_unknown(
    client, route_paths, flush, dispatcher: _CannedDispatcher, store, row
) -> None:
    """A short id two stored cases share names no case, so it is refused."""
    _store_case(store, _SHORT_NAMED_CASE)
    _store_case(store, "https://other.example/cases/VU:42")
    resp = _post(client, route_paths, row, case_id=_CASE_SHORT_ID)
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"]["message"] == (
        f"VulnerabilityCase '{_CASE_SHORT_ID}' not found."
    )
    assert dispatcher.calls == []


def test_canned_dispatcher_conforms_to_the_port(store) -> None:
    """The stub is a ``TriggerDispatcher``: the annotated assignment is the
    static check (mypy, pyright), and a call through the port-typed name
    returns the request's bound result, so the contract tests above exercise
    the same seam the real dispatcher fills."""
    dispatcher: TriggerDispatcher = _CannedDispatcher(store)
    result = dispatcher.trigger(
        AddOnBehalfStatusTriggerRequest(
            actor_id=_ACTOR,
            case_id=_CASE,
            target_actor_id=_OTHER,
            vf_state=CS_vf.Vf,
        ),
        outbox_store(store),
    )
    assert result == _CANNED[StatusResult]
