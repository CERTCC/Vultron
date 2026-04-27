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

Verifies TB-01 through TB-07 requirements from specs/triggerable-behaviors.yaml.
"""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from vultron.adapters.driving.fastapi.routers.trigger_case import (
    _actor_dl,
    _canonical_actor_dl,
)
from vultron.adapters.driving.fastapi.routers import (
    trigger_case as trigger_case_router,
)
from vultron.adapters.utils import parse_id
from vultron.core.states.rm import RM
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

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
    from vultron.adapters.driven.datalayer_sqlite import (
        SqliteDataLayer,
        reset_datalayer,
    )

    actor_obj = as_Service(name="Vendor Co")
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
def client_triggers(dl):
    app = FastAPI()
    app.include_router(trigger_case_router.router)
    app.dependency_overrides[_actor_dl] = lambda: dl
    app.dependency_overrides[_canonical_actor_dl] = lambda: dl
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


@pytest.fixture
def case_with_participant(dl, actor):
    """Create a VulnerabilityCase with the actor as a CaseParticipant.

    The participant is pre-seeded to RM.VALID so that engage/defer triggers
    can apply valid VALID → ACCEPTED / VALID → DEFERRED transitions.
    """
    case_obj = VulnerabilityCase(name="TEST-CASE-001")
    participant = CaseParticipant(
        attributed_to=actor.id_,
        context=case_obj.id_,
    )
    participant.append_rm_state(
        RM.RECEIVED, actor=actor.id_, context=case_obj.id_
    )
    participant.append_rm_state(
        RM.VALID, actor=actor.id_, context=case_obj.id_
    )
    case_obj.case_participants.append(participant.id_)
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
        f"/actors/{actor.id_}/trigger/engage-case",
        json={"case_id": case_with_participant.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_engage_case_response_contains_activity_key(
    client_triggers, actor, case_with_participant
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/engage-case",
        json={"case_id": case_with_participant.id_},
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
        f"/actors/{actor.id_}/trigger/engage-case",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_engage_case_ignores_unknown_fields(
    client_triggers, actor, case_with_participant
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/engage-case",
        json={"case_id": case_with_participant.id_, "unknown_xyz": 99},
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
        f"/actors/{actor.id_}/trigger/engage-case",
        json={"case_id": "urn:uuid:nonexistent-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_engage_case_invalid_case_id_returns_422(
    client_triggers, actor
):
    """engage-case with a non-URI case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/engage-case",
        json={"case_id": "not-a-uri"},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_engage_case_adds_activity_to_outbox(
    client_triggers, dl, actor, case_with_participant
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    actor_before = dl.read(actor.id_)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/engage-case",
        json={"case_id": case_with_participant.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.id_)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_engage_case_updates_participant_rm_state(
    client_triggers, dl, actor, case_with_participant
):
    """engage-case transitions actor's CaseParticipant RM state to ACCEPTED."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/engage-case",
        json={"case_id": case_with_participant.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_with_participant.id_)
    participant_ids = [
        (p if isinstance(p, str) else p.id_)
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
            else getattr(actor_ref, "id_", str(actor_ref))
        )
        if p_actor_id == actor.id_ and p_obj.participant_statuses:
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
            f"/actors/{actor.id_}/trigger/engage-case",
            json={"case_id": case_without_participant.id_},
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
        f"/actors/{actor.id_}/trigger/defer-case",
        json={"case_id": case_with_participant.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_defer_case_response_contains_activity_key(
    client_triggers, actor, case_with_participant
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/defer-case",
        json={"case_id": case_with_participant.id_},
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
        f"/actors/{actor.id_}/trigger/defer-case",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_defer_case_ignores_unknown_fields(
    client_triggers, actor, case_with_participant
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/defer-case",
        json={"case_id": case_with_participant.id_, "extra": "ignored"},
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
        f"/actors/{actor.id_}/trigger/defer-case",
        json={"case_id": "urn:uuid:nonexistent"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_defer_case_invalid_case_id_returns_422(
    client_triggers, actor
):
    """defer-case with a non-URI case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/defer-case",
        json={"case_id": "not-a-uri"},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_defer_case_adds_activity_to_outbox(
    client_triggers, dl, actor, case_with_participant
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    actor_before = dl.read(actor.id_)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/defer-case",
        json={"case_id": case_with_participant.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.id_)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_defer_case_updates_participant_rm_state(
    client_triggers, dl, actor, case_with_participant
):
    """defer-case transitions actor's CaseParticipant RM state to DEFERRED."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/defer-case",
        json={"case_id": case_with_participant.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_with_participant.id_)
    participant_ids = [
        (p if isinstance(p, str) else p.id_)
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
            else getattr(actor_ref, "id_", str(actor_ref))
        )
        if p_actor_id == actor.id_ and p_obj.participant_statuses:
            latest = p_obj.participant_statuses[-1]
            if latest.rm_state == RM.DEFERRED:
                found_deferred = True
                break
    assert found_deferred, "Participant RM state was not updated to DEFERRED"


# ===========================================================================
# Tests for outbox delivery scheduling (D5-6-TRIGDELIV)
# ===========================================================================


class TestTriggerCaseOutboxScheduling:
    """D5-6-TRIGDELIV: case trigger endpoints must schedule outbox_handler."""

    def test_engage_case_schedules_outbox_handler(
        self, client_triggers, actor, case_with_participant
    ):
        """engage-case schedules outbox delivery after execution."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_case.outbox_handler",
            new_callable=AsyncMock,
        ) as mock_outbox:
            resp = client_triggers.post(
                f"/actors/{actor.id_}/trigger/engage-case",
                json={"case_id": case_with_participant.id_},
            )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        mock_outbox.assert_called_once()
        assert mock_outbox.call_args.args[0] == actor.id_

    def test_defer_case_schedules_outbox_handler(
        self, client_triggers, actor, case_with_participant
    ):
        """defer-case schedules outbox delivery after execution."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_case.outbox_handler",
            new_callable=AsyncMock,
        ) as mock_outbox:
            resp = client_triggers.post(
                f"/actors/{actor.id_}/trigger/defer-case",
                json={"case_id": case_with_participant.id_},
            )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        mock_outbox.assert_called_once()
        assert mock_outbox.call_args.args[0] == actor.id_


# ===========================================================================
# Regression tests for BUG-2026040901 — outbox delivery silently dropped
# ===========================================================================


class TestTriggerCaseOutboxCanonicalId:
    """Regression tests for BUG-2026040901.

    The bug: trigger routes receive ``actor_id`` as a short UUID from the URL
    path, but use-case helpers write to the outbox using the canonical full URI
    (``actor.id_``).  If ``outbox_handler`` is called with the short UUID, it
    reads from a different TinyDB table and finds nothing — silently dropping
    all outbox activities.

    Fix: ``_canonical_actor_dl`` resolves the actor from the DataLayer and
    returns an actor-scoped DataLayer keyed by the canonical URI, which is then
    passed to ``outbox_handler``.
    """

    def test_engage_case_canonical_actor_dl_resolves_full_uri(
        self, dl, actor, case_with_participant
    ):
        """outbox_handler receives the canonical-URI-keyed DataLayer.

        When the URL uses a short UUID (last path segment of actor.id_),
        _canonical_actor_dl must resolve to the full URI so that
        outbox_handler reads from the same table as record_outbox_item.
        """
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        short_uuid = actor.id_.rstrip("/").rsplit("/", 1)[-1]

        # Fresh app WITHOUT overriding _canonical_actor_dl so the real
        # dependency resolves the canonical URI via the real DataLayer.
        app = FastAPI()
        app.include_router(trigger_case_router.router)
        app.dependency_overrides[_actor_dl] = lambda: dl
        # _canonical_actor_dl intentionally NOT overridden.

        captured_dl_arg = []

        async def capture_outbox(actor_id, actor_dl, shared_dl):
            captured_dl_arg.append((actor_id, actor_dl))

        import pytest

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "vultron.adapters.driving.fastapi.routers"
                ".trigger_case.outbox_handler",
                capture_outbox,
            )
            client = TestClient(app)
            resp = client.post(
                f"/actors/{short_uuid}/trigger/engage-case",
                json={"case_id": case_with_participant.id_},
            )

        assert resp.status_code == 202, resp.json()
        assert len(captured_dl_arg) == 1, "outbox_handler was not called"
        _, actor_dl_used = captured_dl_arg[0]
        # The actor-scoped DL must be keyed by the FULL canonical URI
        assert actor_dl_used._actor_id == actor.id_, (
            f"Expected canonical URI '{actor.id_}', "
            f"got '{actor_dl_used._actor_id}'"
        )


# ===========================================================================
# Fixtures for create-case and add-report-to-case
# ===========================================================================


@pytest.fixture
def report(dl):
    """Create a persisted VulnerabilityReport for use in tests."""
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report_obj = VulnerabilityReport(
        name="TEST-REPORT-001",
        content="Vulnerability description",
    )
    dl.create(report_obj)
    return report_obj


@pytest.fixture
def http_actor(dl):
    """Create a URL-form actor to match demo trigger path behavior."""
    actor_obj = as_Service(
        id_="https://example.test/api/v2/actors/vendor-http",
        name="Vendor Co HTTP",
    )
    dl.create(actor_obj)
    return actor_obj


# ===========================================================================
# Tests for trigger/create-case
# ===========================================================================


def test_trigger_create_case_returns_202(client_triggers, actor):
    """TB-01-002: POST /actors/{id}/trigger/create-case returns HTTP 202."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/create-case",
        json={"name": "Case-001", "content": "Case content"},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_create_case_response_contains_activity(
    client_triggers, actor
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/create-case",
        json={"name": "Case-001", "content": "Case content"},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_create_case_with_report_id(client_triggers, actor, report):
    """Create-case with optional report_id returns 202."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/create-case",
        json={
            "name": "Case-001",
            "content": "Case content",
            "report_id": report.id_,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_create_case_missing_name_returns_422(client_triggers, actor):
    """TB-03-001: Missing required field returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/create-case",
        json={"content": "Case content"},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_create_case_ignores_unknown_fields(client_triggers, actor):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/create-case",
        json={"name": "Case-001", "content": "Case content", "extra": 99},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_create_case_unknown_actor_returns_404(client_triggers):
    """TB-01-003: Unknown actor_id returns HTTP 404."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/create-case",
        json={"name": "Case-001", "content": "Case content"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_create_case_short_actor_id_updates_outbox_without_warning(
    client_triggers, dl, http_actor, caplog
):
    """Short actor IDs should still update the canonical actor outbox."""
    import logging

    short_uuid = parse_id(http_actor.id_)["object_id"]
    actor_before = dl.read(http_actor.id_)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    with caplog.at_level(logging.WARNING):
        resp = client_triggers.post(
            f"/actors/{short_uuid}/trigger/create-case",
            json={"name": "Case-001", "content": "Case content"},
        )

    assert resp.status_code == status.HTTP_202_ACCEPTED
    actor_after = dl.read(http_actor.id_)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1
    assert not any(
        "add_activity_to_outbox" in record.message for record in caplog.records
    )


# ===========================================================================
# Tests for trigger/add-report-to-case
# ===========================================================================


def test_trigger_add_report_to_case_returns_202(
    client_triggers, actor, case_with_participant, report
):
    """TB-01-002: POST /actors/{id}/trigger/add-report-to-case returns 202."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/add-report-to-case",
        json={
            "case_id": case_with_participant.id_,
            "report_id": report.id_,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_add_report_to_case_response_contains_activity(
    client_triggers, actor, case_with_participant, report
):
    """TB-04-001: Successful trigger response contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/add-report-to-case",
        json={
            "case_id": case_with_participant.id_,
            "report_id": report.id_,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data


def test_trigger_add_report_to_case_missing_report_id_returns_422(
    client_triggers, actor, case_with_participant
):
    """TB-03-001: Missing report_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/add-report-to-case",
        json={"case_id": case_with_participant.id_},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_add_report_to_case_unknown_case_returns_404(
    client_triggers, actor, report
):
    """TB-01-003: Unknown case_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/add-report-to-case",
        json={
            "case_id": "urn:uuid:nonexistent-case",
            "report_id": report.id_,
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_add_report_to_case_unknown_report_returns_404(
    client_triggers, actor, case_with_participant
):
    """TB-01-003: Unknown report_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/add-report-to-case",
        json={
            "case_id": case_with_participant.id_,
            "report_id": "urn:uuid:nonexistent-report",
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_add_report_short_actor_id_updates_outbox_without_warning(
    client_triggers, dl, http_actor, case_with_participant, report, caplog
):
    """Short actor IDs should not break add-report outbox updates."""
    import logging

    short_uuid = parse_id(http_actor.id_)["object_id"]
    actor_before = dl.read(http_actor.id_)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    with caplog.at_level(logging.WARNING):
        resp = client_triggers.post(
            f"/actors/{short_uuid}/trigger/add-report-to-case",
            json={
                "case_id": case_with_participant.id_,
                "report_id": report.id_,
            },
        )

    assert resp.status_code == status.HTTP_202_ACCEPTED
    actor_after = dl.read(http_actor.id_)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1
    assert not any(
        "add_activity_to_outbox" in record.message for record in caplog.records
    )
