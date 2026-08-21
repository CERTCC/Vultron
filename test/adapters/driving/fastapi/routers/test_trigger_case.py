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
from unittest.mock import AsyncMock, patch

from vultron.adapters.driving.fastapi.deps import (
    get_canonical_actor_dl,
    get_trigger_dl,
    get_trigger_service,
)
from vultron.adapters.driving.fastapi.routers import (
    trigger_case as trigger_case_router,
)
from vultron.core.use_cases.triggers.service import TriggerService
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
# Module-level fixture: suppress outbox delivery retries
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_outbox_delivery():
    """Suppress real outbox delivery for every test in this module.

    ``outbox_handler`` uses HTTP with exponential-backoff retries. When
    tests run with non-existent recipient URLs the retry sleeps add ~3.5 s
    per test. Patching to a no-op ``AsyncMock`` eliminates that overhead
    while keeping the scheduler logic testable.

    Tests in ``TestCaseTriggerOutboxScheduling`` that need a trackable mock
    use ``unittest.mock.patch`` as a context manager inside the test body,
    which overrides this fixture's patch for the duration of that context.
    """
    with patch(
        "vultron.adapters.driving.fastapi.routers"
        ".trigger_case.outbox_handler",
        new_callable=AsyncMock,
    ):
        yield


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client_triggers(dl):
    app = FastAPI()
    app.include_router(trigger_case_router.router)
    app.dependency_overrides[get_trigger_service] = lambda: TriggerService(
        dl, trigger_activity=TriggerActivityAdapter(dl)
    )
    app.dependency_overrides[get_trigger_dl] = lambda: dl
    app.dependency_overrides[get_canonical_actor_dl] = lambda: dl
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


@pytest.fixture
def case_with_participant(dl, actor):
    """Create a as_VulnerabilityCase with the actor as a as_CaseParticipant.

    The participant is pre-seeded to RM.VALID so that engage/defer triggers
    can apply valid VALID → ACCEPTED / VALID → DEFERRED transitions.
    """
    case_obj = as_VulnerabilityCase(name="TEST-CASE-001")
    participant = as_CaseParticipant(
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
    case_obj.actor_participant_index[actor.id_] = participant.id_
    dl.create(case_obj)
    dl.create(participant)
    _add_case_manager(case_obj, dl)
    return case_obj


@pytest.fixture
def case_without_participant(dl):
    """Create a as_VulnerabilityCase with a Case Manager but no participant for the actor."""
    case_obj = as_VulnerabilityCase(name="TEST-CASE-NO-PARTICIPANT")
    dl.create(case_obj)
    _add_case_manager(case_obj, dl)
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
    outbox_before = set(dl.outbox_list())

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/engage-case",
        json={"case_id": case_with_participant.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    outbox_after = set(dl.outbox_list())
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_engage_case_updates_participant_rm_state(
    client_triggers, dl, actor, case_with_participant
):
    """engage-case transitions actor's as_CaseParticipant RM state to ACCEPTED."""
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
            if latest.rm.state == RM.ACCEPTED:
                found_accepted = True
                break
    assert found_accepted, "Participant RM state was not updated to ACCEPTED"


def test_trigger_engage_case_no_participant_returns_422(
    client_triggers, actor, case_without_participant, caplog
):
    """engage-case returns 422 when actor has no participant record in the case.

    Pre-#712: the RM update silently failed and 202 was returned anyway.
    Post-#712: the RM transition node is inside the BT; when it fails the BT
    raises VultronValidationError which the router translates to HTTP 422.
    """
    import logging

    with caplog.at_level(logging.WARNING):
        resp = client_triggers.post(
            f"/actors/{actor.id_}/trigger/engage-case",
            json={"case_id": case_without_participant.id_},
        )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
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
    outbox_before = set(dl.outbox_list())

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/defer-case",
        json={"case_id": case_with_participant.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    outbox_after = set(dl.outbox_list())
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_defer_case_updates_participant_rm_state(
    client_triggers, dl, actor, case_with_participant
):
    """defer-case transitions actor's as_CaseParticipant RM state to DEFERRED."""
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
            if latest.rm.state == RM.DEFERRED:
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
    """The URL path segment must resolve to the canonical actor URI.

    Originally a regression test for BUG-2026040901, where a queue written
    under the canonical URI was read under the short path segment and the
    activities vanished. That *class* of bug is now unreachable: ADR-0070
    dropped the ``actor_id`` column, so a queue lives in its owner's store
    rather than in a bucket named by one spelling of an id.

    What still needs pinning is the resolution itself. ``get_canonical_actor_dl``
    turns a short path segment into the canonical URI, and it is that URI which
    selects the store ``outbox_handler`` drains. Get it wrong and the handler
    opens a different — empty — store, which is the same silent drop by a
    different route.
    """

    def test_engage_case_canonical_actor_dl_resolves_full_uri(
        self, dl, actor, case_with_participant
    ):
        """outbox_handler receives the canonical-URI-keyed DataLayer.

        When the URL uses a short UUID (last path segment of actor.id_),
        get_canonical_actor_dl must resolve to the full URI, because that URI
        is what selects the store the handler drains.
        """
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        short_uuid = actor.id_.rstrip("/").rsplit("/", 1)[-1]

        # Fresh app — override get_trigger_service but NOT
        # get_canonical_actor_dl, so the real dependency resolves the canonical
        # URI via the real DataLayer.
        app = FastAPI()
        app.include_router(trigger_case_router.router)
        app.dependency_overrides[get_trigger_service] = lambda: TriggerService(
            dl, trigger_activity=TriggerActivityAdapter(dl)
        )
        # get_canonical_actor_dl intentionally NOT overridden.

        captured_dl_arg = []

        async def capture_outbox(actor_id, actor_dl):
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
    """Create a persisted as_VulnerabilityReport for use in tests."""
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report_obj = as_VulnerabilityReport(
        name="TEST-REPORT-001",
        content="Vulnerability description",
    )
    dl.create(report_obj)
    return report_obj


@pytest.fixture
def short_id_env(report):
    """An actor addressable by its short path segment, with its own store.

    A trigger route resolves its ``{actor_id}`` path segment by *computation* —
    ``base_url + "actors/" + segment``, no registry and no cross-actor scan
    (ADR-0070 decision 2).  Only an actor whose id already has that shape can be
    reached by its short id at all.

    That rules out both actors this test used to be written against.  The
    ``actor`` fixture's id is a ``urn:uuid:``, and the old ``http_actor``'s was
    under ``https://example.test/…``; either way the segment resolves to a
    *different* actor under this node's base URL, holding a different store.  The
    test could not have been fixed by scoping a fixture, because the actor it
    addressed was not addressable here.

    So this derives the id from ``canonical_actor_uri`` and puts the actor, the
    case and the report in that actor's own store — which is the store the BT
    writes and therefore the store the outbox assertion must read.
    """
    from types import SimpleNamespace

    from fastapi import Path as FastAPIPath

    from vultron.adapters.driven.actor_hosts import canonical_actor_uri
    from vultron.adapters.driven.datalayer_sqlite import (
        get_datalayer,
        reset_datalayer,
    )

    segment = "vendor-http"
    actor_id = canonical_actor_uri(segment)
    reset_datalayer(actor_id)

    def _in_memory_actor_dl(actor_id: str = FastAPIPath(...)):
        """Route per actor, in memory.

        A single fixed store would defeat the routing under test: the point is
        that the segment selects *which* store, so every actor id must not
        resolve to the same rows.  Only the backing URL is replaced.
        """
        return get_datalayer(
            canonical_actor_uri(actor_id), db_url="sqlite:///:memory:"
        )

    store = get_datalayer(actor_id, db_url="sqlite:///:memory:")
    store.clear_all()
    actor_obj = as_Service(id_=actor_id, name="Vendor Co HTTP")
    store.create(actor_obj)
    store.create(report)

    case_obj = as_VulnerabilityCase(name="TEST-CASE-SHORT-ID")
    participant = as_CaseParticipant(
        attributed_to=actor_id, context=case_obj.id_
    )
    participant.append_rm_state(
        RM.RECEIVED, actor=actor_id, context=case_obj.id_
    )
    participant.append_rm_state(RM.VALID, actor=actor_id, context=case_obj.id_)
    case_obj.case_participants.append(participant.id_)
    case_obj.actor_participant_index[actor_id] = participant.id_
    store.create(case_obj)
    store.create(participant)
    _add_case_manager(case_obj, store)

    app = FastAPI()
    app.include_router(trigger_case_router.router)
    app.dependency_overrides[get_trigger_dl] = _in_memory_actor_dl
    app.dependency_overrides[get_canonical_actor_dl] = _in_memory_actor_dl
    client = TestClient(app)
    yield SimpleNamespace(
        client=client,
        segment=segment,
        actor=actor_obj,
        store=store,
        case=case_obj,
        report=report,
    )
    app.dependency_overrides = {}
    reset_datalayer(actor_id)


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
    short_id_env, caplog
):
    """A short actor id in the path still queues to that actor's own outbox."""
    import logging

    outbox_before = set(short_id_env.store.outbox_list())

    with caplog.at_level(logging.WARNING):
        resp = short_id_env.client.post(
            f"/actors/{short_id_env.segment}/trigger/create-case",
            json={"name": "Case-001", "content": "Case content"},
        )

    assert resp.status_code == status.HTTP_202_ACCEPTED
    outbox_after = set(short_id_env.store.outbox_list())
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
    short_id_env, caplog
):
    """A short actor id in the path does not break add-report outbox updates."""
    import logging

    outbox_before = set(short_id_env.store.outbox_list())

    with caplog.at_level(logging.WARNING):
        resp = short_id_env.client.post(
            f"/actors/{short_id_env.segment}/trigger/add-report-to-case",
            json={
                "case_id": short_id_env.case.id_,
                "report_id": short_id_env.report.id_,
            },
        )

    assert resp.status_code == status.HTTP_202_ACCEPTED
    outbox_after = set(short_id_env.store.outbox_list())
    assert len(outbox_after - outbox_before) >= 1
    assert not any(
        "add_activity_to_outbox" in record.message for record in caplog.records
    )


# ===========================================================================
# Tests for trigger/add-object-to-case  (TRIG-10-001)
# ===========================================================================


def test_trigger_add_object_to_case_returns_202(
    client_triggers, actor, case_with_participant, report
):
    """TB-01-002: POST /actors/{id}/trigger/add-object-to-case returns 202."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/add-object-to-case",
        json={
            "case_id": case_with_participant.id_,
            "object_id": report.id_,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_add_object_to_case_response_contains_activity(
    client_triggers, actor, case_with_participant, report
):
    """TB-04-001: Response body contains 'activity' key (TRIG-10-001)."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/add-object-to-case",
        json={
            "case_id": case_with_participant.id_,
            "object_id": report.id_,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_add_object_to_case_missing_object_id_returns_422(
    client_triggers, actor, case_with_participant
):
    """Missing object_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/add-object-to-case",
        json={"case_id": case_with_participant.id_},
    )
    assert resp.status_code == 422


def test_trigger_add_object_to_case_unknown_object_returns_404(
    client_triggers, actor, case_with_participant
):
    """TB-01-003: Unknown object_id returns HTTP 404 (TRIG-10-001)."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/add-object-to-case",
        json={
            "case_id": case_with_participant.id_,
            "object_id": "urn:uuid:nonexistent-object",
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_add_object_to_case_unknown_case_returns_404(
    client_triggers, actor, report
):
    """TB-01-003: Unknown case_id returns HTTP 404 (TRIG-10-001)."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/add-object-to-case",
        json={
            "case_id": "urn:uuid:nonexistent-case",
            "object_id": report.id_,
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_add_object_to_case_extra_fields_ignored(
    client_triggers, actor, case_with_participant, report
):
    """Extra request body fields are silently ignored (TB-03-002)."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/add-object-to-case",
        json={
            "case_id": case_with_participant.id_,
            "object_id": report.id_,
            "unexpected_field": "ignored",
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
