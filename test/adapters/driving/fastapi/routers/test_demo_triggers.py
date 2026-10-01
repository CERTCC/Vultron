#!/usr/bin/env python

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

"""
Tests for the demo-only trigger endpoints
(POST /actors/{actor_id}/demo/add-note-to-case and
 POST /actors/{actor_id}/demo/sync-log-entry).

Verifies TRIG-09-001 through TRIG-09-005, TRIG-10-003, TRIG-10-004.
"""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from vultron.adapters.utils import strip_id_prefix
from vultron.adapters.driving.fastapi.deps import get_trigger_dl
from vultron.adapters.driving.fastapi.routers import (
    demo_triggers as demo_triggers_router,
)
from vultron.adapters.driving.fastapi.routers import (
    trigger_case as trigger_case_router,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def _route_key(object_id: str) -> str:
    return strip_id_prefix(object_id)


def _add_case_manager(case: as_VulnerabilityCase, dl) -> as_Service:
    """Add a CASE_MANAGER participant to *case* and return the case actor."""
    case_actor = as_Service(name=f"Case Actor for {case.name}")
    dl.create(case_actor)
    cm_participant = as_CaseParticipant(
        attributed_to=case_actor.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(cm_participant)
    case.actor_participant_index[case_actor.id_] = cm_participant.id_
    dl.save(case)
    return case_actor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def actor_and_dl():
    """Create actor + per-actor DataLayer together."""
    from vultron.adapters.driven.datalayer_sqlite import (
        SqliteDataLayer,
        reset_datalayer,
    )

    actor_obj = as_Service(name="Demo Actor Co")
    actor_id = actor_obj.id_
    reset_datalayer(actor_id)
    actor_dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    actor_dl.clear_all()
    actor_dl.create(actor_obj)
    yield actor_obj, actor_dl
    actor_dl.close()
    reset_datalayer(actor_id)


@pytest.fixture
def actor(actor_and_dl):
    actor_obj, _ = actor_and_dl
    return actor_obj


@pytest.fixture
def dl(actor_and_dl):
    _, actor_dl = actor_and_dl
    return actor_dl


@pytest.fixture
def client_demo(dl):
    """Test client with only the demo router mounted.

    Patches ``get_default_emitter`` with a no-op ``AsyncMock`` so that the
    ``outbox_handler`` background task completes immediately without making
    real HTTP delivery attempts (which would add retry-backoff delays and
    exceed the CI per-test timeout).
    """
    from unittest.mock import AsyncMock, patch

    app = FastAPI()
    app.include_router(demo_triggers_router.router)
    app.dependency_overrides[get_trigger_dl] = lambda: dl
    mock_emitter = AsyncMock()
    with patch(
        "vultron.adapters.driving.fastapi.outbox_handler.get_default_emitter",
        return_value=mock_emitter,
    ):
        yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def client_trigger_only(dl):
    """Test client with only general trigger router — no demo routes."""
    app = FastAPI()
    app.include_router(trigger_case_router.router)
    app.dependency_overrides[get_trigger_dl] = lambda: dl
    yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def case_with_actor(dl, actor):
    """Create a as_VulnerabilityCase listing the actor as a participant."""
    case_obj = as_VulnerabilityCase(name="TEST-DEMO-CASE-001")
    participant = as_CaseParticipant(
        attributed_to=actor.id_,
        context=case_obj.id_,
    )
    case_obj.case_participants.append(participant.id_)
    case_obj.actor_participant_index[actor.id_] = participant.id_
    dl.create(case_obj)
    dl.create(participant)
    _add_case_manager(case_obj, dl)
    return case_obj


# ---------------------------------------------------------------------------
# Tests: POST /actors/{actor_id}/demo/add-note-to-case  (TRIG-09-001, -003,
#                                                         TRIG-10-003)
# ---------------------------------------------------------------------------


class TestDemoAddNoteToCase:
    """Tests for the demo add-note-to-case endpoint."""

    def test_returns_202_on_success(
        self, client_demo: TestClient, actor, case_with_actor
    ):
        """Returns HTTP 202 when request is valid (TRIG-09-001)."""
        response = client_demo.post(
            f"/actors/{actor.id_}/demo/add-note-to-case",
            json={
                "case_id": case_with_actor.id_,
                "note_name": "Test Note",
                "note_content": "This is a test note.",
            },
        )
        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_response_contains_note_and_activity(
        self, client_demo: TestClient, actor, case_with_actor
    ):
        """Response body contains 'note' and 'activity' keys."""
        response = client_demo.post(
            f"/actors/{actor.id_}/demo/add-note-to-case",
            json={
                "case_id": case_with_actor.id_,
                "note_name": "Test Note",
                "note_content": "Content here.",
            },
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "note" in data
        assert "activity" in data

    def test_missing_note_name_returns_422(
        self, client_demo: TestClient, actor, case_with_actor
    ):
        """Missing note_name returns HTTP 422."""
        response = client_demo.post(
            f"/actors/{actor.id_}/demo/add-note-to-case",
            json={
                "case_id": case_with_actor.id_,
                "note_content": "Content only.",
            },
        )
        assert response.status_code == 422

    def test_missing_note_content_returns_422(
        self, client_demo: TestClient, actor, case_with_actor
    ):
        """Missing note_content returns HTTP 422."""
        response = client_demo.post(
            f"/actors/{actor.id_}/demo/add-note-to-case",
            json={
                "case_id": case_with_actor.id_,
                "note_name": "Note title",
            },
        )
        assert response.status_code == 422

    def test_extra_fields_ignored(
        self, client_demo: TestClient, actor, case_with_actor
    ):
        """Unknown fields in the request body are silently ignored (TB-03-002)."""
        response = client_demo.post(
            f"/actors/{actor.id_}/demo/add-note-to-case",
            json={
                "case_id": case_with_actor.id_,
                "note_name": "Test Note",
                "note_content": "Content.",
                "unexpected_field": "ignored",
            },
        )
        assert response.status_code == status.HTTP_202_ACCEPTED


class TestDemoAddNoteToCaseNotAtTriggerPrefix:
    """Verify add-note-to-case is absent from the /trigger/ path (TRIG-10-003)."""

    def test_add_note_not_at_trigger_prefix(
        self, client_trigger_only: TestClient, actor, case_with_actor
    ):
        """POST /actors/{id}/trigger/add-note-to-case returns HTTP 404."""
        response = client_trigger_only.post(
            f"/actors/{actor.id_}/trigger/add-note-to-case",
            json={
                "case_id": case_with_actor.id_,
                "note_name": "Test",
                "note_content": "Body.",
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Tests: POST /actors/{actor_id}/demo/sync-log-entry  (TRIG-09-001, -003,
#                                                       TRIG-10-004)
# ---------------------------------------------------------------------------


@pytest.fixture
def managed_case(dl, actor):
    """A case the demo ``actor`` manages, so its store holds the canonical log.

    ``attributed_to`` mints the per-case genesis hash the first commit anchors
    on (CLP-08-005).
    """
    case = as_VulnerabilityCase(name="Sync Demo Case", attributed_to=actor.id_)
    cm = as_CaseParticipant(
        attributed_to=actor.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.actor_participant_index[actor.id_] = cm.id_
    case.case_participants.append(cm.id_)
    dl.create(case)
    dl.create(cm)
    return case


class TestDemoSyncLogEntry:
    """The route runs ``SvcSyncLogEntryUseCase`` through the trigger
    dispatcher; the response contract is unchanged (TRIG-12-003)."""

    @pytest.mark.spec("TRIG-10-004")
    @pytest.mark.spec("SYNC-02-002")
    def test_returns_202_with_the_entry_identity(
        self, client_demo: TestClient, dl, actor, managed_case
    ):
        resp = client_demo.post(
            f"/actors/{actor.id_}/demo/sync-log-entry",
            json={
                "case_id": managed_case.id_,
                "object_id": managed_case.id_,
                "event_type": "demo_sync",
            },
        )
        assert resp.status_code == status.HTTP_202_ACCEPTED, resp.text
        body = resp.json()
        assert set(body) == {
            "log_entry_id",
            "entry_hash",
            "log_index",
            "emitting_actor_id",
        }
        assert body["log_index"] == 0
        assert body["emitting_actor_id"] == actor.id_
        entry = dl.read(body["log_entry_id"])
        assert entry is not None
        assert entry.entry_hash == body["entry_hash"]
        assert entry.event_type == "demo_sync"

    @pytest.mark.spec("TRIG-01-003")
    def test_unknown_actor_returns_404(
        self, client_demo: TestClient, managed_case
    ):
        resp = client_demo.post(
            "/actors/nonexistent-actor/demo/sync-log-entry",
            json={
                "case_id": managed_case.id_,
                "object_id": managed_case.id_,
                "event_type": "demo_sync",
            },
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.json()["detail"]["error"] == "NotFound"

    def test_missing_event_type_returns_422(
        self, client_demo: TestClient, actor, managed_case
    ):
        resp = client_demo.post(
            f"/actors/{actor.id_}/demo/sync-log-entry",
            json={"case_id": managed_case.id_, "object_id": managed_case.id_},
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.spec("CM-24-001")
    @pytest.mark.spec("TRIG-07-001")
    def test_requester_that_is_not_the_manager_drains_the_managers_outbox(
        self, client_demo: TestClient, dl, actor
    ):
        """Single-server shape: the commit runs as a hosted CASE_MANAGER, so
        the flush the route schedules drains *that* actor's outbox."""
        from vultron.adapters.driven.datalayer_sqlite import reset_datalayer

        cm_actor = as_Service(name="Hosted Case Manager")
        reset_datalayer(cm_actor.id_)
        cm_dl = dl.clone_for_actor(cm_actor.id_)
        cm_dl.clear_all()
        try:
            cm_dl.create(cm_actor)
            case = as_VulnerabilityCase(
                name="Managed Elsewhere", attributed_to=cm_actor.id_
            )
            cm = as_CaseParticipant(
                attributed_to=cm_actor.id_,
                context=case.id_,
                case_roles=[CVDRole.CASE_MANAGER],
            )
            me = as_CaseParticipant(
                attributed_to=actor.id_,
                context=case.id_,
                case_roles=[CVDRole.REPORTER],
            )
            for participant_actor_id, participant in (
                (cm_actor.id_, cm),
                (actor.id_, me),
            ):
                case.actor_participant_index[participant_actor_id] = (
                    participant.id_
                )
                case.case_participants.append(participant.id_)
            for store in (dl, cm_dl):
                store.create(case)
                store.create(cm)
                store.create(me)

            resp = client_demo.post(
                f"/actors/{actor.id_}/demo/sync-log-entry",
                json={
                    "case_id": case.id_,
                    "object_id": case.id_,
                    "event_type": "single_server",
                },
            )

            assert resp.status_code == status.HTTP_202_ACCEPTED, resp.text
            body = resp.json()
            assert body["emitting_actor_id"] == cm_actor.id_
            assert cm_dl.read(body["log_entry_id"]) is not None
            # The background flush ran against the CASE_MANAGER's store: the
            # fan-out it queued there has been popped for delivery.
            assert cm_dl.outbox_list() == []
            assert dl.outbox_list() == []
        finally:
            cm_dl.clear_all()
            reset_datalayer(cm_actor.id_)

    def test_store_without_the_canonical_log_answers_500(
        self, client_demo: TestClient, dl, actor
    ):
        """The case's CASE_MANAGER is elsewhere, so the ledger-authority guard
        declines the mint and the route keeps its historical 500."""
        foreign_cm = "https://elsewhere.example/actors/other-cm"
        case = as_VulnerabilityCase(
            name="Foreign Case", attributed_to=foreign_cm
        )
        cm = as_CaseParticipant(
            attributed_to=foreign_cm,
            context=case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case.actor_participant_index[foreign_cm] = cm.id_
        case.case_participants.append(cm.id_)
        dl.create(case)
        dl.create(cm)

        resp = client_demo.post(
            f"/actors/{actor.id_}/demo/sync-log-entry",
            json={
                "case_id": case.id_,
                "object_id": case.id_,
                "event_type": "foreign",
            },
        )
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert resp.json() == {"detail": "Log entry commit did not persist."}


# ---------------------------------------------------------------------------
# Fixtures and helpers for case ledger endpoint tests
# ---------------------------------------------------------------------------


def _make_log_entry(dl, case_id: str, log_index: int) -> object:
    """Create and save a CaseLedgerEntry directly to the DataLayer."""
    from vultron.core.models.case_ledger_entry import CaseLedgerEntry

    entry = CaseLedgerEntry(
        case_id=case_id,
        log_index=log_index,
        log_object_id=f"{case_id}/objects/{log_index}",
        event_type=f"test_event_{log_index}",
    )
    dl.save(entry)
    return entry


# ---------------------------------------------------------------------------
# Tests: GET /actors/{actor_id}/demo/cases/{case_id}/log
# ---------------------------------------------------------------------------


class TestDemoGetCaseLedger:
    """Tests for GET /actors/{actor_id}/demo/cases/{case_id}/log."""

    def test_returns_200_empty_list_when_no_entries(
        self, client_demo: TestClient, actor, case_with_actor
    ):
        """Returns HTTP 200 and empty array when no log entries exist."""
        response = client_demo.get(
            f"/actors/{actor.id_}/demo/cases/"
            f"{_route_key(case_with_actor.id_)}/log"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_returns_entries_sorted_by_log_index(
        self, client_demo: TestClient, actor, case_with_actor, dl
    ):
        """Returns entries in ascending log_index order."""
        _make_log_entry(dl, case_with_actor.id_, log_index=2)
        _make_log_entry(dl, case_with_actor.id_, log_index=0)
        _make_log_entry(dl, case_with_actor.id_, log_index=1)

        response = client_demo.get(
            f"/actors/{actor.id_}/demo/cases/"
            f"{_route_key(case_with_actor.id_)}/log"
        )
        assert response.status_code == status.HTTP_200_OK
        entries = response.json()
        assert len(entries) == 3
        assert [e["logIndex"] for e in entries] == [0, 1, 2]

    def test_only_returns_entries_for_requested_case(
        self, client_demo: TestClient, actor, case_with_actor, dl
    ):
        """Entries from other cases are not included in the response."""
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        other_case = as_VulnerabilityCase(name="OTHER-CASE")
        dl.create(other_case)
        _make_log_entry(dl, case_with_actor.id_, log_index=0)
        _make_log_entry(dl, other_case.id_, log_index=0)

        response = client_demo.get(
            f"/actors/{actor.id_}/demo/cases/"
            f"{_route_key(case_with_actor.id_)}/log"
        )
        entries = response.json()
        assert len(entries) == 1
        assert entries[0]["caseId"] == case_with_actor.id_

    def test_ndjson_via_accept_header(
        self, client_demo: TestClient, actor, case_with_actor, dl
    ):
        """Returns NDJSON when Accept: application/x-ndjson is requested."""
        import json as _json

        _make_log_entry(dl, case_with_actor.id_, log_index=0)
        _make_log_entry(dl, case_with_actor.id_, log_index=1)

        response = client_demo.get(
            f"/actors/{actor.id_}/demo/cases/"
            f"{_route_key(case_with_actor.id_)}/log",
            headers={"accept": "application/x-ndjson"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"].startswith(
            "application/x-ndjson"
        )
        lines = response.text.strip().split("\n")
        assert len(lines) == 2
        parsed = [_json.loads(line) for line in lines]
        assert parsed[0]["logIndex"] == 0
        assert parsed[1]["logIndex"] == 1

    def test_ndjson_via_format_query_param(
        self, client_demo: TestClient, actor, case_with_actor, dl
    ):
        """Returns NDJSON when ?format=ndjson query param is set."""
        import json as _json

        _make_log_entry(dl, case_with_actor.id_, log_index=0)

        response = client_demo.get(
            f"/actors/{actor.id_}/demo/cases/"
            f"{_route_key(case_with_actor.id_)}/log",
            params={"format": "ndjson"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"].startswith(
            "application/x-ndjson"
        )
        parsed = _json.loads(response.text.strip())
        assert parsed["logIndex"] == 0

    def test_list_with_http_url_case_id_surrogate_key(
        self, client_demo: TestClient, actor, dl
    ):
        """Resolves HTTP URL case IDs through their surrogate key."""
        http_case_id = "https://example.org/cases/demo/123"
        case = as_VulnerabilityCase(id_=http_case_id, name="HTTP Case")
        dl.create(case)
        _make_log_entry(dl, http_case_id, log_index=0)
        _make_log_entry(dl, http_case_id, log_index=1)

        response = client_demo.get(
            f"/actors/{actor.id_}/demo/cases/{_route_key(http_case_id)}/log"
        )
        assert response.status_code == status.HTTP_200_OK
        entries = response.json()
        assert len(entries) == 2
        assert all(e["caseId"] == http_case_id for e in entries)
        assert [e["logIndex"] for e in entries] == [0, 1]


# ---------------------------------------------------------------------------
# Tests: GET /actors/{actor_id}/demo/cases/{case_id}/log/{index}
# ---------------------------------------------------------------------------


class TestDemoGetCaseLedgerEntry:
    """Tests for GET /actors/{actor_id}/demo/cases/{case_id}/log/{index}."""

    def test_returns_correct_entry(
        self, client_demo: TestClient, actor, case_with_actor, dl
    ):
        """Returns HTTP 200 and the correct log entry for a valid index."""
        _make_log_entry(dl, case_with_actor.id_, log_index=0)
        _make_log_entry(dl, case_with_actor.id_, log_index=1)

        response = client_demo.get(
            f"/actors/{actor.id_}/demo/cases/"
            f"{_route_key(case_with_actor.id_)}/log/1"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["logIndex"] == 1
        assert data["caseId"] == case_with_actor.id_
        assert data["eventType"] == "test_event_1"

    def test_returns_404_for_missing_index(
        self, client_demo: TestClient, actor, case_with_actor
    ):
        """Returns HTTP 404 when no entry exists at the given index."""
        response = client_demo.get(
            f"/actors/{actor.id_}/demo/cases/"
            f"{_route_key(case_with_actor.id_)}/log/99"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_negative_index_returns_422(
        self, client_demo: TestClient, actor, case_with_actor
    ):
        """Negative index returns HTTP 422 (Path(ge=0) validation)."""
        response = client_demo.get(
            f"/actors/{actor.id_}/demo/cases/"
            f"{_route_key(case_with_actor.id_)}/log/-1"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_single_entry_with_http_url_case_id_surrogate_key(
        self, client_demo: TestClient, actor, dl
    ):
        """Resolves HTTP URL case IDs through their surrogate key."""
        http_case_id = "https://example.org/cases/demo/456"
        case = as_VulnerabilityCase(id_=http_case_id, name="HTTP Case")
        dl.create(case)
        _make_log_entry(dl, http_case_id, log_index=0)

        response = client_demo.get(
            f"/actors/{actor.id_}/demo/cases/{_route_key(http_case_id)}/log/0"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["logIndex"] == 0
        assert data["caseId"] == http_case_id

    def test_response_uses_camelcase_aliases(
        self, client_demo: TestClient, actor, case_with_actor, dl
    ):
        """Response uses camelCase serialization aliases (by_alias=True)."""
        _make_log_entry(dl, case_with_actor.id_, log_index=0)

        response = client_demo.get(
            f"/actors/{actor.id_}/demo/cases/"
            f"{_route_key(case_with_actor.id_)}/log/0"
        )
        data = response.json()
        # camelCase aliases should be present
        assert "logObjectId" in data
        assert "eventType" in data
        assert "logIndex" in data
        assert "caseId" in data
        assert "log_object_id" not in data
        assert "event_type" not in data


# ---------------------------------------------------------------------------
# Tests: POST /actors/{actor_id}/demo/close-case  (TRIG-09-001, DEMOMA-07-001)
# ---------------------------------------------------------------------------


class TestDemoCloseCase:
    """Tests for the demo close-case endpoint."""

    def test_returns_202_on_success(
        self, client_demo: TestClient, actor, case_with_actor
    ):
        """Successful close-case returns 202 Accepted."""
        response = client_demo.post(
            f"/actors/{actor.id_}/demo/close-case",
            json={"case_id": case_with_actor.id_},
        )
        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_leave_activity_in_response(
        self, client_demo: TestClient, actor, case_with_actor
    ):
        """Response body contains a Leave activity with correct type and actor fields."""
        response = client_demo.post(
            f"/actors/{actor.id_}/demo/close-case",
            json={"case_id": case_with_actor.id_},
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "activity" in data, "Response must contain 'activity' key"
        activity = data["activity"]
        assert (
            activity.get("type") == "Leave"
        ), f"Activity type must be 'Leave'; got {activity.get('type')}"
        assert (
            activity.get("actor") == actor.id_
        ), f"Activity actor must be actor.id_; got {activity.get('actor')}"

    def test_rm_not_closed_at_send_time(
        self, client_demo: TestClient, actor, case_with_actor, dl
    ):
        """RM.CLOSED must NOT appear at send time — only after ledger round-trip (AC-2)."""
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.states.rm import RM

        client_demo.post(
            f"/actors/{actor.id_}/demo/close-case",
            json={"case_id": case_with_actor.id_},
        )
        case = dl.read(case_with_actor.id_)
        assert isinstance(case, VulnerabilityCase)
        participant_id = case.actor_participant_index.get(actor.id_)
        assert (
            participant_id is not None
        ), "actor must have a participant entry in actor_participant_index"
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant), (
            f"dl.read({participant_id!r}) must return CaseParticipant;"
            f" got {type(participant)}"
        )
        rm_states = [
            ps.rm.state
            for ps in participant.participant_statuses
            if hasattr(ps, "rm") and ps.rm is not None
        ]
        assert RM.CLOSED not in rm_states, (
            "RM.CLOSED must not be set at send time (AC-2);"
            f" rm_states={rm_states}"
        )

    def test_unknown_case_returns_404(self, client_demo: TestClient, actor):
        """Request for a non-existent case must return 404."""
        response = client_demo.post(
            f"/actors/{actor.id_}/demo/close-case",
            json={"case_id": "urn:uuid:no-such-case"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
