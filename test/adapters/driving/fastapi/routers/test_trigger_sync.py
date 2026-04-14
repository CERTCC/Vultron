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
Tests for the sync trigger endpoint
(POST /actors/{actor_id}/trigger/sync-log-entry).

Verifies TB-01 through TB-07 requirements from specs/triggerable-behaviors.md
and SYNC-02-002, SYNC-02-003 from specs/sync-log-replication.md.
"""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from vultron.adapters.driving.fastapi.routers.trigger_sync import (
    _actor_dl,
    _canonical_actor_dl,
)
from vultron.adapters.driving.fastapi.routers import (
    trigger_sync as trigger_sync_router,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def actor_and_dl():
    """Create actor + shared DataLayer together."""
    from vultron.adapters.driven.datalayer_sqlite import (
        SqliteDataLayer,
        reset_datalayer,
    )

    actor_obj = as_Service(name="CaseActor Co")
    actor_id = actor_obj.id_
    reset_datalayer(actor_id)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    dl.clear_all()
    dl.create(actor_obj)
    yield actor_obj, dl
    dl.clear_all()
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
def client_triggers(dl):
    app = FastAPI()
    app.include_router(trigger_sync_router.router)
    app.dependency_overrides[_actor_dl] = lambda: dl
    app.dependency_overrides[_canonical_actor_dl] = lambda: dl
    yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def case_with_actor(dl, actor):
    """Create a VulnerabilityCase that lists the actor as a participant."""
    from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant

    case_obj = VulnerabilityCase(name="TEST-SYNC-CASE-001")
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
# Tests: POST /actors/{actor_id}/trigger/sync-log-entry
# ---------------------------------------------------------------------------


class TestTriggerSyncLogEntry:
    """Tests for the sync-log-entry trigger endpoint."""

    def test_returns_202_on_success(
        self, client_triggers: TestClient, actor, case_with_actor
    ):
        """Returns HTTP 202 Accepted when request is valid (TB-01-001)."""
        response = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "test_event",
            },
        )
        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_response_contains_entry_fields(
        self, client_triggers: TestClient, actor, case_with_actor
    ):
        """Response includes log_entry_id, entry_hash, and log_index (TB-04-001)."""
        response = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "test_event",
            },
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
        body = response.json()
        assert "log_entry_id" in body
        assert "entry_hash" in body
        assert "log_index" in body

    def test_log_entry_id_contains_case_id(
        self, client_triggers: TestClient, actor, case_with_actor
    ):
        """The committed entry ID is scoped to the case (SYNC-02-002)."""
        response = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "test_event",
            },
        )
        body = response.json()
        assert case_with_actor.id_ in body["log_entry_id"]

    def test_log_index_starts_at_one(
        self, client_triggers: TestClient, actor, case_with_actor
    ):
        """First log entry for a case gets log_index 0 (SYNC-02-002)."""
        response = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "first_event",
            },
        )
        assert response.json()["log_index"] == 0

    def test_sequential_entries_have_increasing_log_index(
        self, client_triggers: TestClient, actor, case_with_actor
    ):
        """Sequential commits for the same case increment log_index."""
        r1 = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "event_a",
            },
        )
        r2 = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "event_b",
            },
        )
        assert r1.json()["log_index"] < r2.json()["log_index"]

    def test_entry_hash_is_non_empty_string(
        self, client_triggers: TestClient, actor, case_with_actor
    ):
        """entry_hash is a non-empty string (SYNC-02-003)."""
        response = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "hash_test",
            },
        )
        hash_val = response.json()["entry_hash"]
        assert isinstance(hash_val, str)
        assert len(hash_val) > 0

    def test_sequential_entries_have_different_hashes(
        self, client_triggers: TestClient, actor, case_with_actor
    ):
        """Each committed entry produces a distinct entry_hash."""
        r1 = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "event_x",
            },
        )
        r2 = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "event_y",
            },
        )
        assert r1.json()["entry_hash"] != r2.json()["entry_hash"]

    def test_missing_case_id_returns_422(
        self, client_triggers: TestClient, actor
    ):
        """Missing required field case_id returns 422 Unprocessable Entity."""
        response = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={"object_id": "https://example.org/obj", "event_type": "x"},
        )
        assert response.status_code == 422

    def test_missing_object_id_returns_422(
        self, client_triggers: TestClient, actor, case_with_actor
    ):
        """Missing required field object_id returns 422."""
        response = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "event_type": "test",
            },
        )
        assert response.status_code == 422

    def test_missing_event_type_returns_422(
        self, client_triggers: TestClient, actor, case_with_actor
    ):
        """Missing required field event_type returns 422."""
        response = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
            },
        )
        assert response.status_code == 422

    def test_unknown_fields_are_ignored(
        self, client_triggers: TestClient, actor, case_with_actor
    ):
        """Extra fields in the request body are silently ignored (TB-03-002)."""
        response = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "test_event",
                "unexpected_field": "should be ignored",
            },
        )
        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_entry_persisted_in_datalayer(
        self, client_triggers: TestClient, actor, case_with_actor, dl
    ):
        """The committed VultronCaseLogEntry is stored in the DataLayer."""
        response = client_triggers.post(
            f"/actors/{actor.id_}/trigger/sync-log-entry",
            json={
                "case_id": case_with_actor.id_,
                "object_id": case_with_actor.id_,
                "event_type": "persistence_test",
            },
        )
        entry_id = response.json()["log_entry_id"]
        stored = dl.read(entry_id)
        assert stored is not None
