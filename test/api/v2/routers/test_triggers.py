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
Tests for the trigger endpoints (POST /actors/{actor_id}/trigger/{behavior}).

Verifies TB-01 through TB-07 requirements from specs/triggerable-behaviors.md.
"""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from vultron.api.v2.data.actor_io import init_actor_io
from vultron.api.v2.data.status import ReportStatus, set_status
from vultron.api.v2.datalayer.db_record import object_to_record
from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
from vultron.api.v2.routers import triggers as triggers_router
from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.base.objects.actors import as_Service
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
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
    app.include_router(triggers_router.router)
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
def report(dl, actor):
    report_obj = VulnerabilityReport(
        name="Test Vulnerability",
        content="Test content",
    )
    dl.create(report_obj)
    return report_obj


@pytest.fixture
def offer(dl, report, actor):
    offer_obj = as_Offer(
        actor=actor.as_id,
        object=report.as_id,
        target=actor.as_id,
    )
    dl.create(offer_obj)
    return offer_obj


@pytest.fixture
def received_report(report, actor):
    """Put the report into RM.RECEIVED state."""
    set_status(
        ReportStatus(
            object_type="VulnerabilityReport",
            object_id=report.as_id,
            actor_id=actor.as_id,
            status=RM.RECEIVED,
        )
    )
    return report


# ---------------------------------------------------------------------------
# TB-01-001 / TB-01-002: Endpoint exists and returns 202
# ---------------------------------------------------------------------------


def test_trigger_validate_report_returns_202(
    client_triggers, actor, offer, received_report
):
    """TB-01-002: POST /actors/{id}/trigger/validate-report returns HTTP 202."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/validate-report",
        json={"offer_id": offer.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


# ---------------------------------------------------------------------------
# TB-04-001: Response body contains "activity" key
# ---------------------------------------------------------------------------


def test_trigger_validate_report_response_contains_activity_key(
    client_triggers, actor, offer, received_report
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/validate-report",
        json={"offer_id": offer.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data


# ---------------------------------------------------------------------------
# TB-03-001: Missing required offer_id returns 422
# ---------------------------------------------------------------------------


def test_trigger_validate_report_missing_offer_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing offer_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/validate-report",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# TB-03-002: Unknown fields in request body are ignored
# ---------------------------------------------------------------------------


def test_trigger_validate_report_ignores_unknown_fields(
    client_triggers, actor, offer, received_report
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/validate-report",
        json={
            "offer_id": offer.as_id,
            "unknown_field_xyz": "should_be_ignored",
            "another_unknown": 42,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


# ---------------------------------------------------------------------------
# TB-01-003: Unknown actor returns 404 with structured error
# ---------------------------------------------------------------------------


def test_trigger_validate_report_unknown_actor_returns_404(client_triggers):
    """TB-01-003: Unknown actor_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/validate-report",
        json={"offer_id": "urn:uuid:any-offer"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert "detail" in data
    assert data["detail"]["status"] == 404
    assert data["detail"]["error"] == "NotFound"
    assert "message" in data["detail"]
    assert data["detail"]["activity_id"] is None


# ---------------------------------------------------------------------------
# TB-01-003: Unknown offer_id returns 404 with structured error
# ---------------------------------------------------------------------------


def test_trigger_validate_report_unknown_offer_returns_404(
    client_triggers, actor
):
    """TB-01-003: Unknown offer_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/validate-report",
        json={"offer_id": "urn:uuid:nonexistent-offer"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


# ---------------------------------------------------------------------------
# TB-03-003: Optional note field is accepted
# ---------------------------------------------------------------------------


def test_trigger_validate_report_with_note_returns_202(
    client_triggers, actor, offer, received_report
):
    """TB-03-003: Optional note field is accepted and does not cause errors."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/validate-report",
        json={"offer_id": offer.as_id, "note": "Validated after review."},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


# ---------------------------------------------------------------------------
# TB-06-001 / TB-06-002: DataLayer injected via dependency
# ---------------------------------------------------------------------------


def test_trigger_validate_report_uses_injected_datalayer(
    datalayer, actor, offer, received_report
):
    """TB-06-001, TB-06-002: DataLayer is resolved from Depends(get_datalayer)."""
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer as gdl

    app = FastAPI()
    app.include_router(triggers_router.router)

    call_log = []

    def tracking_dl():
        call_log.append("called")
        return datalayer

    app.dependency_overrides[gdl] = tracking_dl
    client = TestClient(app)
    client.post(
        f"/actors/{actor.as_id}/trigger/validate-report",
        json={"offer_id": offer.as_id},
    )
    app.dependency_overrides = {}

    assert len(call_log) >= 1, "get_datalayer was not called"


# ---------------------------------------------------------------------------
# TB-07-001: Resulting activity is added to actor's outbox
# ---------------------------------------------------------------------------


def test_trigger_validate_report_adds_activity_to_outbox(
    client_triggers, dl, actor, offer, received_report
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    actor_before = dl.read(actor.as_id)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/validate-report",
        json={"offer_id": offer.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.as_id)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    new_items = outbox_after - outbox_before
    assert len(new_items) >= 1, "No new activity was added to the outbox"
