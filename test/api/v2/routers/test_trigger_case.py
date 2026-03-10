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
Tests for the case trigger endpoints
(POST /actors/{actor_id}/trigger/{engage,defer}-case).

Verifies TB-01 through TB-07 requirements from specs/triggerable-behaviors.md.
"""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from vultron.api.v2.data.actor_io import init_actor_io
from vultron.api.v2.datalayer.db_record import object_to_record
from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
from vultron.api.v2.routers import trigger_case as trigger_case_router
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.bt.report_management.states import RM

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dl(datalayer):
    return datalayer


@pytest.fixture
def client_triggers(dl):
    app = FastAPI()
    app.include_router(trigger_case_router.router)
    app.dependency_overrides[get_datalayer] = lambda: dl
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


@pytest.fixture
def actor(dl):
    actor_obj = as_Service(name="Vendor Co")
    dl.create(object_to_record(actor_obj))
    init_actor_io(actor_obj.as_id)
    return actor_obj


@pytest.fixture
def case_with_participant(dl, actor):
    """Create a VulnerabilityCase with the actor as a CaseParticipant."""
    case_obj = VulnerabilityCase(name="TEST-CASE-001")
    participant = CaseParticipant(
        attributed_to=actor.as_id,
        context=case_obj.as_id,
    )
    case_obj.case_participants.append(participant.as_id)
    dl.create(case_obj)
    dl.create(participant)
    return case_obj


@pytest.fixture
def case_without_participant(dl):
    """Create a VulnerabilityCase with no CaseParticipant for the actor."""
    case_obj = VulnerabilityCase(name="TEST-CASE-NO-PARTICIPANT")
    dl.create(case_obj)
    return case_obj


# ===========================================================================
# Tests for trigger/engage-case
# ===========================================================================


def test_trigger_engage_case_returns_202(
    client_triggers, actor, case_with_participant
):
    """TB-01-002: POST /actors/{id}/trigger/engage-case returns HTTP 202."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/engage-case",
        json={"case_id": case_with_participant.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_engage_case_response_contains_activity_key(
    client_triggers, actor, case_with_participant
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/engage-case",
        json={"case_id": case_with_participant.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_engage_case_missing_case_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/engage-case",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_engage_case_ignores_unknown_fields(
    client_triggers, actor, case_with_participant
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/engage-case",
        json={"case_id": case_with_participant.as_id, "unknown_xyz": 99},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_engage_case_unknown_actor_returns_404(client_triggers):
    """TB-01-003: Unknown actor_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/engage-case",
        json={"case_id": "urn:uuid:any-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"
    assert data["detail"]["activity_id"] is None


def test_trigger_engage_case_unknown_case_returns_404(client_triggers, actor):
    """TB-01-003: Unknown case_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/engage-case",
        json={"case_id": "urn:uuid:nonexistent-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_engage_case_adds_activity_to_outbox(
    client_triggers, dl, actor, case_with_participant
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    actor_before = dl.read(actor.as_id)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/engage-case",
        json={"case_id": case_with_participant.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.as_id)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_engage_case_updates_participant_rm_state(
    client_triggers, dl, actor, case_with_participant
):
    """engage-case transitions actor's CaseParticipant RM state to ACCEPTED."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/engage-case",
        json={"case_id": case_with_participant.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_with_participant.as_id)
    participant_ids = [
        (p if isinstance(p, str) else p.as_id)
        for p in updated_case.case_participants
    ]
    found_accepted = False
    for p_id in participant_ids:
        p_obj = dl.read(p_id)
        if p_obj is None:
            continue
        actor_ref = p_obj.attributed_to
        p_actor_id = (
            actor_ref
            if isinstance(actor_ref, str)
            else getattr(actor_ref, "as_id", str(actor_ref))
        )
        if p_actor_id == actor.as_id and p_obj.participant_statuses:
            latest = p_obj.participant_statuses[-1]
            if latest.rm_state == RM.ACCEPTED:
                found_accepted = True
                break
    assert found_accepted, "Participant RM state was not updated to ACCEPTED"


def test_trigger_engage_case_no_participant_returns_202_with_warning(
    client_triggers, actor, case_without_participant, caplog
):
    """engage-case succeeds and warns when actor has no participant record."""
    import logging

    with caplog.at_level(logging.WARNING):
        resp = client_triggers.post(
            f"/actors/{actor.as_id}/trigger/engage-case",
            json={"case_id": case_without_participant.as_id},
        )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    assert any("participant" in r.message.lower() for r in caplog.records)


# ===========================================================================
# Tests for trigger/defer-case
# ===========================================================================


def test_trigger_defer_case_returns_202(
    client_triggers, actor, case_with_participant
):
    """TB-01-002: POST /actors/{id}/trigger/defer-case returns HTTP 202."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/defer-case",
        json={"case_id": case_with_participant.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_defer_case_response_contains_activity_key(
    client_triggers, actor, case_with_participant
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/defer-case",
        json={"case_id": case_with_participant.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_defer_case_missing_case_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/defer-case",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_defer_case_ignores_unknown_fields(
    client_triggers, actor, case_with_participant
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/defer-case",
        json={"case_id": case_with_participant.as_id, "extra": "ignored"},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_defer_case_unknown_actor_returns_404(client_triggers):
    """TB-01-003: Unknown actor_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        "/actors/nonexistent/trigger/defer-case",
        json={"case_id": "urn:uuid:any"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_defer_case_unknown_case_returns_404(client_triggers, actor):
    """TB-01-003: Unknown case_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/defer-case",
        json={"case_id": "urn:uuid:nonexistent"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_defer_case_adds_activity_to_outbox(
    client_triggers, dl, actor, case_with_participant
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    actor_before = dl.read(actor.as_id)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/defer-case",
        json={"case_id": case_with_participant.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.as_id)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_defer_case_updates_participant_rm_state(
    client_triggers, dl, actor, case_with_participant
):
    """defer-case transitions actor's CaseParticipant RM state to DEFERRED."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/defer-case",
        json={"case_id": case_with_participant.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_with_participant.as_id)
    participant_ids = [
        (p if isinstance(p, str) else p.as_id)
        for p in updated_case.case_participants
    ]
    found_deferred = False
    for p_id in participant_ids:
        p_obj = dl.read(p_id)
        if p_obj is None:
            continue
        actor_ref = p_obj.attributed_to
        p_actor_id = (
            actor_ref
            if isinstance(actor_ref, str)
            else getattr(actor_ref, "as_id", str(actor_ref))
        )
        if p_actor_id == actor.as_id and p_obj.participant_statuses:
            latest = p_obj.participant_statuses[-1]
            if latest.rm_state == RM.DEFERRED:
                found_deferred = True
                break
    assert found_deferred, "Participant RM state was not updated to DEFERRED"
