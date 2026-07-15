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
from vultron.adapters.driving.fastapi.deps import (
    get_canonical_actor_dl,
    get_trigger_dl,
    get_trigger_service,
)
from vultron.enums.roles import CVDRole
from vultron.core.use_cases.triggers.service import TriggerService
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.wire.as2.factories import rm_invite_to_case_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    VulnerabilityCaseStub,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client_triggers(dl):
    app = FastAPI()
    app.include_router(trigger_actor_router.router)
    app.dependency_overrides[get_trigger_service] = lambda: TriggerService(
        dl, trigger_activity=TriggerActivityAdapter(dl)
    )
    app.dependency_overrides[get_trigger_dl] = lambda: dl
    app.dependency_overrides[get_canonical_actor_dl] = lambda: dl
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
    """Create and persist a as_VulnerabilityCase with a CASE_MANAGER participant."""
    case_actor = as_Service(name="Case Actor")
    dl.create(case_actor)
    case = as_VulnerabilityCase(name="TEST-CASE-001")
    owner_participant = as_CaseParticipant(
        attributed_to=actor.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_OWNER],
    )
    case_manager_participant = as_CaseParticipant(
        attributed_to=case_actor.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.actor_participant_index[actor.id_] = owner_participant.id_
    case.actor_participant_index[case_actor.id_] = case_manager_participant.id_
    case.case_participants.append(owner_participant.id_)
    case.case_participants.append(case_manager_participant.id_)
    dl.create(case)
    dl.create(owner_participant)
    dl.create(case_manager_participant)
    return case


@pytest.fixture
def case_obj_with_case_actor(dl, actor):
    """Case + Case Actor service for offer-case-manager-role tests.

    Identical to ``case_obj`` but also persists the Case Actor service with
    ``context=case.id_`` so that ``_find_case_actor_id`` can resolve it.
    """
    case_actor = as_Service(name="Case Actor Service")
    dl.create(case_actor)
    case = as_VulnerabilityCase(name="TEST-CASE-OCM")
    owner_participant = as_CaseParticipant(
        attributed_to=actor.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_OWNER],
    )
    case_manager_participant = as_CaseParticipant(
        attributed_to=case_actor.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.actor_participant_index[actor.id_] = owner_participant.id_
    case.actor_participant_index[case_actor.id_] = case_manager_participant.id_
    case.case_participants.append(owner_participant.id_)
    case.case_participants.append(case_manager_participant.id_)
    dl.create(case)
    dl.create(owner_participant)
    dl.create(case_manager_participant)
    # Update the Case Actor Service with context=case.id_ so that
    # _find_case_actor_id resolves it for this case.
    case_actor_with_context = as_Service(
        id_=case_actor.id_,
        name="Case Actor Service",
        context=case.id_,
    )
    dl.save(case_actor_with_context)
    return case, case_actor


@pytest.fixture
def invite(dl, actor, case_obj, other_actor):
    """Create and persist an RmInviteToCaseActivity for accept-case-invite tests."""
    invite_activity = rm_invite_to_case_activity(
        other_actor,
        target=VulnerabilityCaseStub(id_=case_obj.id_),
        actor=actor.id_,
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


# ===========================================================================
# Tests for trigger/offer-case-manager-role
# ===========================================================================


def test_trigger_offer_case_manager_role_returns_202(
    client_triggers, actor, case_obj_with_case_actor
):
    """TB-01-002: POST /actors/{id}/trigger/offer-case-manager-role returns 202."""
    case, _ = case_obj_with_case_actor
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/offer-case-manager-role",
        json={"case_id": case.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_offer_case_manager_role_response_contains_activity(
    client_triggers, actor, case_obj_with_case_actor
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    case, _ = case_obj_with_case_actor
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/offer-case-manager-role",
        json={"case_id": case.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None
    assert data["activity"]["type"] == "Offer"


def test_trigger_offer_case_manager_role_activity_actor_is_case_actor(
    client_triggers, actor, case_obj_with_case_actor
):
    """Offer activity must be emitted from the Case Actor's identity (PCR-08-007)."""
    case, case_actor = case_obj_with_case_actor
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/offer-case-manager-role",
        json={"case_id": case.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert data["activity"]["actor"] == case_actor.id_


def test_trigger_offer_case_manager_role_missing_case_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Missing case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/offer-case-manager-role",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_offer_case_manager_role_unknown_actor_returns_404(
    client_triggers,
):
    """TB-01-003: Unknown actor_id returns HTTP 404."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/offer-case-manager-role",
        json={"case_id": "urn:uuid:any-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_offer_case_manager_role_unknown_case_returns_404(
    client_triggers, actor
):
    """TB-01-003: Unknown case_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/offer-case-manager-role",
        json={"case_id": "urn:uuid:nonexistent-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_offer_case_manager_role_no_case_actor_returns_404(
    client_triggers, actor, case_obj
):
    """TB-01-003: No Case Actor for the case returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/offer-case-manager-role",
        json={"case_id": case_obj.id_},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
