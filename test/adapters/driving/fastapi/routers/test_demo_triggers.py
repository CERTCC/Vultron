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

from vultron.adapters.driving.fastapi.deps import (
    get_canonical_actor_dl,
    get_trigger_dl,
    get_trigger_service,
)
from vultron.adapters.driving.fastapi.routers import (
    demo_triggers as demo_triggers_router,
)
from vultron.adapters.driving.fastapi.routers import (
    trigger_case as trigger_case_router,
)
from vultron.core.use_cases.triggers.service import TriggerService
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

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
    """Test client with only the demo router mounted."""
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )

    app = FastAPI()
    app.include_router(demo_triggers_router.router)
    app.dependency_overrides[get_trigger_service] = lambda: TriggerService(
        dl,
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
    )
    app.dependency_overrides[get_trigger_dl] = lambda: dl
    app.dependency_overrides[get_canonical_actor_dl] = lambda: dl
    yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def client_trigger_only(dl):
    """Test client with only general trigger router — no demo routes."""
    app = FastAPI()
    app.include_router(trigger_case_router.router)
    app.dependency_overrides[get_trigger_service] = lambda: TriggerService(
        dl, trigger_activity=TriggerActivityAdapter(dl)
    )
    app.dependency_overrides[get_trigger_dl] = lambda: dl
    app.dependency_overrides[get_canonical_actor_dl] = lambda: dl
    yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def case_with_actor(dl, actor):
    """Create a VulnerabilityCase listing the actor as a participant."""
    case_obj = VulnerabilityCase(name="TEST-DEMO-CASE-001")
    participant = CaseParticipant(
        attributed_to=actor.id_,
        context=case_obj.id_,
    )
    case_obj.case_participants.append(participant.id_)
    case_obj.actor_participant_index[actor.id_] = participant.id_
    dl.create(case_obj)
    dl.create(participant)
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


class TestDemoSyncLogEntry:
    """Tests for the demo sync-log-entry endpoint."""

    def test_returns_202_on_success(
        self, client_demo: TestClient, actor, case_with_actor
    ):
        """Returns HTTP 202 Accepted on valid request (TRIG-09-001)."""
        response = client_demo.post(
            f"/actors/{actor.id_}/demo/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "test_event",
            },
        )
        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_response_contains_log_fields(
        self, client_demo: TestClient, actor, case_with_actor
    ):
        """Response body contains log_entry_id, entry_hash, log_index."""
        response = client_demo.post(
            f"/actors/{actor.id_}/demo/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "test_event",
            },
        )
        body = response.json()
        assert "log_entry_id" in body
        assert "entry_hash" in body
        assert "log_index" in body

    def test_missing_case_id_returns_422(self, client_demo: TestClient, actor):
        """Missing case_id returns HTTP 422."""
        response = client_demo.post(
            f"/actors/{actor.id_}/demo/sync-log-entry",
            json={
                "object_id": "https://example.org/obj",
                "event_type": "x",
            },
        )
        assert response.status_code == 422

    def test_extra_fields_ignored(
        self, client_demo: TestClient, actor, case_with_actor
    ):
        """Extra fields are silently ignored (TB-03-002)."""
        response = client_demo.post(
            f"/actors/{actor.id_}/demo/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "test_event",
                "unexpected": "ignored",
            },
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
