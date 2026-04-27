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
Tests for the actor trigger endpoints
(POST /actors/{actor_id}/trigger/{suggest-actor-to-case,accept-case-invite}).

Verifies TB-01 through TB-07 requirements from specs/triggerable-behaviors.yaml.
"""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from vultron.adapters.driving.fastapi.routers import (
    trigger_actor as trigger_actor_router,
)
from vultron.adapters.driving.fastapi.routers.trigger_actor import (
    _actor_dl,
    _canonical_actor_dl,
)
from vultron.wire.as2.vocab.activities.case import RmInviteToCaseActivity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCase,
    VulnerabilityCaseStub,
)

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
    app.include_router(trigger_actor_router.router)
    app.dependency_overrides[_actor_dl] = lambda: dl
    app.dependency_overrides[_canonical_actor_dl] = lambda: dl
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


@pytest.fixture
def other_actor(dl):
    """Create and persist a second actor for suggest-actor tests."""
    other = as_Service(name="Other Actor")
    dl.create(other)
    return other


@pytest.fixture
def case_obj(dl, actor):
    """Create and persist a VulnerabilityCase for tests."""
    case = VulnerabilityCase(name="TEST-CASE-001")
    dl.create(case)
    return case


@pytest.fixture
def invite(dl, actor, case_obj, other_actor):
    """Create and persist an RmInviteToCaseActivity for accept-case-invite tests."""
    invite_activity = RmInviteToCaseActivity(
        actor=actor.id_,
        object_=other_actor,
        target=VulnerabilityCaseStub(id_=case_obj.id_),
    )
    dl.create(invite_activity)
    return invite_activity


# ===========================================================================
# Tests for trigger/suggest-actor-to-case
# ===========================================================================


def test_trigger_suggest_actor_to_case_returns_202(
    client_triggers, actor, case_obj, other_actor
):
    """TB-01-002: POST /actors/{id}/trigger/suggest-actor-to-case returns 202."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/suggest-actor-to-case",
        json={
            "case_id": case_obj.id_,
            "suggested_actor_id": other_actor.id_,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_suggest_actor_to_case_response_contains_activity(
    client_triggers, actor, case_obj, other_actor
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/suggest-actor-to-case",
        json={
            "case_id": case_obj.id_,
            "suggested_actor_id": other_actor.id_,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_suggest_actor_to_case_missing_case_id_returns_422(
    client_triggers, actor, other_actor
):
    """TB-03-001: Missing case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/suggest-actor-to-case",
        json={"suggested_actor_id": other_actor.id_},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_suggest_actor_to_case_ignores_unknown_fields(
    client_triggers, actor, case_obj, other_actor
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/suggest-actor-to-case",
        json={
            "case_id": case_obj.id_,
            "suggested_actor_id": other_actor.id_,
            "extra_field": "ignored",
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_suggest_actor_to_case_unknown_actor_returns_404(
    client_triggers,
):
    """TB-01-003: Unknown actor_id returns HTTP 404."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/suggest-actor-to-case",
        json={
            "case_id": "urn:uuid:any-case",
            "suggested_actor_id": "urn:uuid:any-actor",
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_suggest_actor_to_case_unknown_case_returns_404(
    client_triggers, actor, other_actor
):
    """TB-01-003: Unknown case_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/suggest-actor-to-case",
        json={
            "case_id": "urn:uuid:nonexistent-case",
            "suggested_actor_id": other_actor.id_,
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_suggest_actor_to_case_unknown_suggested_actor_returns_404(
    client_triggers, actor, case_obj
):
    """TB-01-003: Unknown suggested_actor_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/suggest-actor-to-case",
        json={
            "case_id": case_obj.id_,
            "suggested_actor_id": "urn:uuid:nonexistent-actor",
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# Tests for trigger/accept-case-invite
# ===========================================================================


def test_trigger_accept_case_invite_returns_202(
    client_triggers, other_actor, invite, dl
):
    """TB-01-002: POST /actors/{id}/trigger/accept-case-invite returns 202."""
    resp = client_triggers.post(
        f"/actors/{other_actor.id_}/trigger/accept-case-invite",
        json={"invite_id": invite.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_accept_case_invite_response_contains_activity(
    client_triggers, other_actor, invite, dl
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{other_actor.id_}/trigger/accept-case-invite",
        json={"invite_id": invite.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_accept_case_invite_object_is_invite(
    client_triggers, other_actor, invite, dl
):
    """DR-05: Accept activity object_ must be the original invite, not the case."""
    resp = client_triggers.post(
        f"/actors/{other_actor.id_}/trigger/accept-case-invite",
        json={"invite_id": invite.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert data["activity"]["object"]["id"] == invite.id_


def test_trigger_accept_case_invite_missing_invite_id_returns_422(
    client_triggers, other_actor
):
    """TB-03-001: Missing invite_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{other_actor.id_}/trigger/accept-case-invite",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_accept_case_invite_ignores_unknown_fields(
    client_triggers, other_actor, invite, dl
):
    """TB-03-002: Unknown fields are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{other_actor.id_}/trigger/accept-case-invite",
        json={"invite_id": invite.id_, "extra": "ignored"},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_accept_case_invite_unknown_actor_returns_404(
    client_triggers,
):
    """TB-01-003: Unknown actor_id returns HTTP 404."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/accept-case-invite",
        json={"invite_id": "urn:uuid:any-invite"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_accept_case_invite_unknown_invite_returns_404(
    client_triggers, other_actor
):
    """TB-01-003: Unknown invite_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{other_actor.id_}/trigger/accept-case-invite",
        json={"invite_id": "urn:uuid:nonexistent-invite"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
