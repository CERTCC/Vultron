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
Tests for the report trigger endpoints
(POST /actors/{actor_id}/trigger/{validate,invalidate,reject,close}-report).

Verifies TB-01 through TB-07 requirements from specs/triggerable-behaviors.md.
"""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.use_cases._helpers import _report_phase_status_id
from vultron.adapters.driving.fastapi.routers.trigger_report import _actor_dl
from vultron.adapters.driving.fastapi.routers import (
    trigger_report as trigger_report_router,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.core.states.rm import RM

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def actor_and_dl():
    """Create actor + per-actor DataLayer together (avoids chicken-and-egg).

    The actor object is created first (no DataLayer needed), then a
    DataLayer is instantiated scoped to that actor's ID (ADR-0012 Option B).
    The actor is then persisted into its own DataLayer.  Callers should
    unpack via the ``actor`` and ``dl`` fixtures below.
    """
    from vultron.adapters.driven.datalayer_tinydb import (
        TinyDbDataLayer,
        reset_datalayer,
    )

    actor_obj = as_Service(name="Vendor Co")
    actor_id = actor_obj.id_
    reset_datalayer(actor_id)
    actor_dl = TinyDbDataLayer(db_path=None, actor_id=actor_id)
    actor_dl.clear_all()
    actor_dl.create(actor_obj)
    yield actor_obj, actor_dl
    actor_dl.clear_all()
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
    app.include_router(trigger_report_router.router)
    app.dependency_overrides[_actor_dl] = lambda: dl
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


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
        actor=actor.id_,
        object_=report.id_,
        target=actor.id_,
    )
    dl.create(offer_obj)
    return offer_obj


@pytest.fixture
def received_report(dl, actor, report, offer):
    """Pre-create a VulnerabilityCase for the report at RM.RECEIVED.

    Per ADR-0015, the case is created at report receipt.  The validate_report
    BT's EnsureEmbargoExists node requires a case to exist.
    """
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.case.receive_report_case_tree import (
        create_receive_report_case_tree,
    )

    bridge = BTBridge(datalayer=dl)
    tree = create_receive_report_case_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )
    bridge.execute_with_setup(tree, actor_id=actor.id_)
    return report


@pytest.fixture
def invalid_report(report):
    """Put the report into RM.RECEIVED state (for invalidate/reject triggers)."""
    return report


@pytest.fixture
def accepted_report(report):
    """Report in an acceptable state for close-report (no CLOSED record)."""
    return report


@pytest.fixture
def closed_report(dl, report, actor):
    """Put the report into RM.CLOSED state (triggers 409 on close-report)."""
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.CLOSED.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm_state=RM.CLOSED,
    )
    dl.create(status)
    return report


@pytest.fixture
def non_report_object(dl):
    """An EmbargoEvent stored in the datalayer — not an Offer."""
    from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

    obj = EmbargoEvent(context="urn:uuid:some-case")
    dl.create(obj)
    return obj


# ===========================================================================
# Tests for trigger/validate-report
# ===========================================================================


def test_trigger_validate_report_returns_202(
    client_triggers, actor, offer, received_report
):
    """TB-01-002: POST /actors/{id}/trigger/validate-report returns HTTP 202."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/validate-report",
        json={"offer_id": offer.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_validate_report_response_contains_activity_key(
    client_triggers, actor, offer, received_report
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/validate-report",
        json={"offer_id": offer.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data


def test_trigger_validate_report_missing_offer_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing offer_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/validate-report",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_validate_report_ignores_unknown_fields(
    client_triggers, actor, offer, received_report
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/validate-report",
        json={
            "offer_id": offer.id_,
            "unknown_field_xyz": "should_be_ignored",
            "another_unknown": 42,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


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


def test_trigger_validate_report_unknown_offer_returns_404(
    client_triggers, actor
):
    """TB-01-003: Unknown offer_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/validate-report",
        json={"offer_id": "urn:uuid:nonexistent-offer"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_validate_report_with_note_returns_202(
    client_triggers, actor, offer, received_report
):
    """TB-03-003: Optional note field is accepted and does not cause errors."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/validate-report",
        json={"offer_id": offer.id_, "note": "Validated after review."},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_validate_report_uses_injected_datalayer(
    dl, actor, offer, received_report
):
    """TB-06-001, TB-06-002: DataLayer is resolved from Depends(_actor_dl)."""
    from vultron.adapters.driving.fastapi.routers.trigger_report import (
        _actor_dl as gdl,
    )

    app = FastAPI()
    app.include_router(trigger_report_router.router)

    call_log = []

    def tracking_dl():
        call_log.append("called")
        return dl

    app.dependency_overrides[gdl] = tracking_dl
    client = TestClient(app)
    client.post(
        f"/actors/{actor.id_}/trigger/validate-report",
        json={"offer_id": offer.id_},
    )
    app.dependency_overrides = {}

    assert len(call_log) >= 1, "get_datalayer was not called"


def test_trigger_validate_report_transitions_rm_to_valid(
    client_triggers, dl, actor, offer, received_report
):
    """TB-07-001: Successful validate-report trigger transitions RM to VALID.

    Per ADR-0015, case creation (and outbox notifications) now happen at
    RM.RECEIVED via receive_report_case_tree.  The validate-report trigger
    is responsible only for the RM.RECEIVED → RM.VALID transition.
    """
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/validate-report",
        json={"offer_id": offer.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    valid_status_id = _report_phase_status_id(
        actor.id_, offer.object_, RM.VALID.value
    )
    valid_record = dl.get("ParticipantStatus", valid_status_id)
    assert (
        valid_record is not None
    ), "Expected a RM.VALID ParticipantStatus after validate-report trigger"


def test_trigger_validate_report_non_report_offer_returns_422(
    client_triggers, actor, non_report_object
):
    """validate-report rejects an offer_id that is not an Offer of a report."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/validate-report",
        json={"offer_id": non_report_object.id_},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ===========================================================================
# Tests for trigger/invalidate-report
# ===========================================================================


def test_trigger_invalidate_report_returns_202(
    client_triggers, actor, offer, invalid_report
):
    """TB-01-002: POST /actors/{id}/trigger/invalidate-report returns HTTP 202."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/invalidate-report",
        json={"offer_id": offer.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_invalidate_report_response_contains_activity_key(
    client_triggers, actor, offer, invalid_report
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/invalidate-report",
        json={"offer_id": offer.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_invalidate_report_missing_offer_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing offer_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/invalidate-report",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_invalidate_report_ignores_unknown_fields(
    client_triggers, actor, offer, invalid_report
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/invalidate-report",
        json={"offer_id": offer.id_, "unknown_xyz": "ignored"},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_invalidate_report_unknown_actor_returns_404(client_triggers):
    """TB-01-003: Unknown actor_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        "/actors/nonexistent/trigger/invalidate-report",
        json={"offer_id": "urn:uuid:any"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_invalidate_report_unknown_offer_returns_404(
    client_triggers, actor
):
    """TB-01-003: Unknown offer_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/invalidate-report",
        json={"offer_id": "urn:uuid:nonexistent"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_invalidate_report_adds_activity_to_outbox(
    client_triggers, dl, actor, offer, invalid_report
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    actor_before = dl.read(actor.id_)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/invalidate-report",
        json={"offer_id": offer.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.id_)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_invalidate_report_with_note_returns_202(
    client_triggers, actor, offer, invalid_report
):
    """TB-03-003: Optional note field is accepted."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/invalidate-report",
        json={
            "offer_id": offer.id_,
            "note": "Soft-closing; needs more info.",
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_invalidate_report_non_report_offer_returns_422(
    client_triggers, actor, non_report_object
):
    """invalidate-report rejects an offer_id that is not an Offer of a report."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/invalidate-report",
        json={"offer_id": non_report_object.id_},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ===========================================================================
# Tests for trigger/reject-report
# ===========================================================================


def test_trigger_reject_report_returns_202(
    client_triggers, actor, offer, invalid_report
):
    """TB-01-002: POST /actors/{id}/trigger/reject-report returns HTTP 202."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-report",
        json={"offer_id": offer.id_, "note": "Out of scope."},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_reject_report_response_contains_activity_key(
    client_triggers, actor, offer, invalid_report
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-report",
        json={"offer_id": offer.id_, "note": "Out of scope."},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_reject_report_missing_note_returns_422(
    client_triggers, actor, offer, invalid_report
):
    """TB-03-004: reject-report without note field returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-report",
        json={"offer_id": offer.id_},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_reject_report_empty_note_emits_warning(
    client_triggers, actor, offer, invalid_report, caplog
):
    """TB-03-004: reject-report with empty note emits a WARNING."""
    import logging

    with caplog.at_level(logging.WARNING):
        resp = client_triggers.post(
            f"/actors/{actor.id_}/trigger/reject-report",
            json={"offer_id": offer.id_, "note": ""},
        )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    assert any("empty" in r.message.lower() for r in caplog.records)


def test_trigger_reject_report_missing_offer_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing offer_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-report",
        json={"note": "Some reason."},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_reject_report_ignores_unknown_fields(
    client_triggers, actor, offer, invalid_report
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-report",
        json={"offer_id": offer.id_, "note": "Reason.", "extra_field": 42},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_reject_report_unknown_actor_returns_404(client_triggers):
    """TB-01-003: Unknown actor_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        "/actors/nonexistent/trigger/reject-report",
        json={"offer_id": "urn:uuid:any", "note": "Reason."},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_reject_report_unknown_offer_returns_404(
    client_triggers, actor
):
    """TB-01-003: Unknown offer_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-report",
        json={"offer_id": "urn:uuid:nonexistent", "note": "Reason."},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_reject_report_adds_activity_to_outbox(
    client_triggers, dl, actor, offer, invalid_report
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    actor_before = dl.read(actor.id_)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-report",
        json={"offer_id": offer.id_, "note": "Definitively out of scope."},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.id_)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_reject_report_non_report_offer_returns_422(
    client_triggers, actor, non_report_object
):
    """reject-report rejects an offer_id that is not an Offer of a report."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-report",
        json={"offer_id": non_report_object.id_, "note": "Not a report."},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ===========================================================================
# Tests for trigger/close-report
# ===========================================================================


def test_trigger_close_report_returns_202(
    client_triggers, actor, offer, accepted_report
):
    """TB-01-002: POST /actors/{id}/trigger/close-report returns HTTP 202."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/close-report",
        json={"offer_id": offer.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_close_report_response_contains_activity_key(
    client_triggers, actor, offer, accepted_report
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/close-report",
        json={"offer_id": offer.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_close_report_missing_offer_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing offer_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/close-report",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_close_report_ignores_unknown_fields(
    client_triggers, actor, offer, accepted_report
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/close-report",
        json={"offer_id": offer.id_, "unexpected_field": "ignored"},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_close_report_with_note_returns_202(
    client_triggers, actor, offer, accepted_report
):
    """TB-03-003: Optional note field is accepted."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/close-report",
        json={"offer_id": offer.id_, "note": "Resolved upstream."},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_close_report_unknown_actor_returns_404(client_triggers):
    """TB-01-003: Unknown actor_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        "/actors/nonexistent/trigger/close-report",
        json={"offer_id": "urn:uuid:any"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_close_report_unknown_offer_returns_404(
    client_triggers, actor
):
    """TB-01-003: Unknown offer_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/close-report",
        json={"offer_id": "urn:uuid:nonexistent"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_close_report_adds_activity_to_outbox(
    client_triggers, dl, actor, offer, accepted_report
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    actor_before = dl.read(actor.id_)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/close-report",
        json={"offer_id": offer.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.id_)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_close_report_already_closed_returns_409(
    client_triggers, actor, offer, closed_report
):
    """close-report returns HTTP 409 when the report is already CLOSED."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/close-report",
        json={"offer_id": offer.id_},
    )
    assert resp.status_code == status.HTTP_409_CONFLICT
    data = resp.json()
    assert data["detail"]["error"] == "Conflict"


def test_trigger_close_report_non_report_offer_returns_422(
    client_triggers, actor, non_report_object
):
    """close-report rejects an offer_id that is not an Offer of a report."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/close-report",
        json={"offer_id": non_report_object.id_},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ===========================================================================
# Tests for trigger/submit-report
# ===========================================================================


def test_trigger_submit_report_returns_202(client_triggers, actor):
    """TB-04-001: submit-report trigger returns 202 with offer payload."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/submit-report",
        json={
            "report_name": "Remote Code Execution in Widget",
            "report_content": "A critical RCE vulnerability was found.",
            "recipient_id": "https://example.org/actors/vendor",
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    body = resp.json()
    assert "offer" in body
    assert body["offer"]["type"] == "Offer"


def test_trigger_submit_report_creates_report_in_datalayer(
    client_triggers, actor, dl
):
    """submit-report trigger persists a VulnerabilityReport in the DataLayer."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/submit-report",
        json={
            "report_name": "Stored XSS in Dashboard",
            "report_content": "An attacker can inject scripts via the search box.",
            "recipient_id": "https://example.org/actors/vendor",
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    offer_id = resp.json()["offer"]["id"]

    # The offer should be fetchable from the DataLayer.
    stored_offer = dl.read(offer_id)
    assert stored_offer is not None


def test_trigger_submit_report_creates_offer_in_outbox(
    client_triggers, actor, dl
):
    """TB-07-001: submit-report adds the offer to the actor's outbox."""
    actor_before = dl.read(actor.id_)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/submit-report",
        json={
            "report_name": "SQL Injection",
            "report_content": "A SQL injection was found in the login form.",
            "recipient_id": "https://example.org/actors/vendor",
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.id_)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_submit_report_missing_field_returns_422(
    client_triggers, actor
):
    """submit-report rejects a body missing required fields."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/submit-report",
        json={
            "report_name": "Missing content",
            # report_content and recipient_id are missing
        },
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_submit_report_logs_report_and_offer(
    client_triggers, actor, caplog
):
    """submit-report trigger emits INFO logs for report creation and offer."""
    import logging

    with caplog.at_level(logging.INFO, logger="vultron"):
        client_triggers.post(
            f"/actors/{actor.id_}/trigger/submit-report",
            json={
                "report_name": "Heap Buffer Overflow",
                "report_content": "Heap buffer overflow in network parser.",
                "recipient_id": "https://example.org/actors/vendor",
            },
        )

    messages = [r.message for r in caplog.records]
    assert any("Created VulnerabilityReport" in m for m in messages)
    assert any("Offering report" in m for m in messages)


# ===========================================================================
# Tests for outbox delivery scheduling (D5-6-TRIGDELIV)
# ===========================================================================


class TestTriggerReportOutboxScheduling:
    """D5-6-TRIGDELIV: trigger endpoints must schedule outbox_handler."""

    def _make_patches(self):
        """Return context managers that mock outbox_handler and get_datalayer."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_dl = MagicMock()
        return (
            patch(
                "vultron.adapters.driving.fastapi.routers"
                ".trigger_report.outbox_handler",
                new_callable=AsyncMock,
            ),
            patch(
                "vultron.adapters.driving.fastapi.routers"
                ".trigger_report.get_datalayer",
                return_value=mock_dl,
            ),
            mock_dl,
        )

    def test_validate_report_schedules_outbox_handler(
        self, client_triggers, actor, offer
    ):
        """validate-report schedules outbox delivery after execution."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_dl = MagicMock()
        with patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_report.outbox_handler",
            new_callable=AsyncMock,
        ) as mock_outbox, patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_report.get_datalayer",
            return_value=mock_dl,
        ):
            resp = client_triggers.post(
                f"/actors/{actor.id_}/trigger/validate-report",
                json={"offer_id": offer.id_},
            )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        mock_outbox.assert_called_once()
        assert mock_outbox.call_args.args[0] == actor.id_
        assert mock_outbox.call_args.args[1] is mock_dl

    def test_invalidate_report_schedules_outbox_handler(
        self, client_triggers, actor, offer
    ):
        """invalidate-report schedules outbox delivery after execution."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_dl = MagicMock()
        with patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_report.outbox_handler",
            new_callable=AsyncMock,
        ) as mock_outbox, patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_report.get_datalayer",
            return_value=mock_dl,
        ):
            resp = client_triggers.post(
                f"/actors/{actor.id_}/trigger/invalidate-report",
                json={"offer_id": offer.id_},
            )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        mock_outbox.assert_called_once()
        assert mock_outbox.call_args.args[0] == actor.id_

    def test_submit_report_schedules_outbox_handler(
        self, client_triggers, actor
    ):
        """submit-report schedules outbox delivery after execution."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_dl = MagicMock()
        with patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_report.outbox_handler",
            new_callable=AsyncMock,
        ) as mock_outbox, patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_report.get_datalayer",
            return_value=mock_dl,
        ):
            resp = client_triggers.post(
                f"/actors/{actor.id_}/trigger/submit-report",
                json={
                    "report_name": "Test Report",
                    "report_content": "Content.",
                    "recipient_id": "https://example.org/actors/vendor",
                },
            )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        mock_outbox.assert_called_once()
        assert mock_outbox.call_args.args[0] == actor.id_
