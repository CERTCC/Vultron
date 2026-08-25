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

from test.conftest import seed_case_actor_replica
from fastapi import FastAPI, status
from fastapi import Path as FastAPIPath
from fastapi.testclient import TestClient

from vultron.adapters.driving.fastapi.routers import (
    trigger_actor as trigger_actor_router,
)
from vultron.adapters.driving.fastapi.deps import (
    get_canonical_actor_dl,
    get_trigger_dl,
    get_trigger_service,
)
import vultron.adapters.driving.fastapi.outbox_handler as _outbox_handler
from vultron.enums.roles import CVDRole
from vultron.core.use_cases.triggers.service import TriggerService
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
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


class _NoopEmitter:
    async def emit(self, activity, recipients):  # noqa: ARG002
        pass


def _store_for(actor_id: str) -> SqliteDataLayer:
    """Open the addressed actor's own store, as the real dependencies do.

    ``get_trigger_service`` builds its ``TriggerService`` from the store of the
    actor named in the URL, so an override that hands every request one fixed
    store is not a stand-in for the routing — it is a shared multi-tenant store,
    the thing ADR-0072 removes. Two of these endpoints are addressed to an actor
    other than the ``dl`` fixture's, and with one store they read an invitation
    the accepting actor had never received (#2548, DL-07-009).

    Engines are cached on ``(db_url, actor slug)``, so this returns the same
    underlying store as the ``dl`` fixture for that fixture's actor and a
    genuinely separate one for anybody else.
    """
    return SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)


@pytest.fixture
def client_triggers(dl):
    _outbox_handler._default_emitter = _NoopEmitter()
    app = FastAPI()
    app.include_router(trigger_actor_router.router)

    def _service(actor_id: str = FastAPIPath(...)) -> TriggerService:
        store = _store_for(actor_id)
        return TriggerService(
            store, trigger_activity=TriggerActivityAdapter(store)
        )

    def _dl_for_path(actor_id: str = FastAPIPath(...)) -> SqliteDataLayer:
        return _store_for(actor_id)

    app.dependency_overrides[get_trigger_service] = _service
    app.dependency_overrides[get_trigger_dl] = _dl_for_path
    app.dependency_overrides[get_canonical_actor_dl] = _dl_for_path
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}
    _outbox_handler._default_emitter = None


@pytest.fixture
def other_actor_and_dl(dl):
    """A second actor **and its own store** (ADR-0072).

    What this actor knows lives here, not in the inviter's store: an invitation
    addressed to it is something it received. The inviter's store gets the actor
    record too, because an inviter must know the actor it is inviting.
    """
    other = as_Service(name="Other Actor")
    other_dl = _store_for(other.id_)
    other_dl.clear_all()
    other_dl.create(other)
    dl.create(other)
    yield other, other_dl
    other_dl.close()


@pytest.fixture
def other_actor(other_actor_and_dl):
    """Create and persist a second actor for suggest-actor tests."""
    other, _ = other_actor_and_dl
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
def invite(other_actor_and_dl, actor, case_obj):
    """Persist an RmInviteToCaseActivity in the *invitee's* store.

    The invitee is the actor that accepts or rejects, and the accept/reject
    trigger runs against its own store — the one it received the invitation into.
    Seeding the inviter's store instead only worked while the two shared one
    store (#2548, DL-07-009).
    """
    other, other_dl = other_actor_and_dl
    invite_activity = rm_invite_to_case_activity(
        other,
        target=VulnerabilityCaseStub(id_=case_obj.id_),
        actor=actor.id_,
    )
    other_dl.create(invite_activity)
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
# Tests for trigger/reject-case-invite
# ===========================================================================


def test_trigger_reject_case_invite_returns_202(
    client_triggers, other_actor, invite, dl
):
    """TB-01-002: POST /actors/{id}/trigger/reject-case-invite returns 202."""
    resp = client_triggers.post(
        f"/actors/{other_actor.id_}/trigger/reject-case-invite",
        json={"invite_id": invite.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_reject_case_invite_response_contains_activity(
    client_triggers, other_actor, invite, dl
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{other_actor.id_}/trigger/reject-case-invite",
        json={"invite_id": invite.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_reject_case_invite_object_is_invite(
    client_triggers, other_actor, invite, dl
):
    """DR-05: Reject activity object_ must be the original invite, not the case."""
    resp = client_triggers.post(
        f"/actors/{other_actor.id_}/trigger/reject-case-invite",
        json={"invite_id": invite.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert data["activity"]["object"]["id"] == invite.id_


def test_trigger_reject_case_invite_missing_invite_id_returns_422(
    client_triggers, other_actor
):
    """TB-03-001: Missing invite_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{other_actor.id_}/trigger/reject-case-invite",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_reject_case_invite_ignores_unknown_fields(
    client_triggers, other_actor, invite, dl
):
    """TB-03-002: Unknown fields are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{other_actor.id_}/trigger/reject-case-invite",
        json={"invite_id": invite.id_, "extra": "ignored"},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_reject_case_invite_unknown_actor_returns_404(
    client_triggers,
):
    """TB-01-003: Unknown actor_id returns HTTP 404."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/reject-case-invite",
        json={"invite_id": "urn:uuid:any-invite"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_reject_case_invite_unknown_invite_returns_404(
    client_triggers, other_actor
):
    """TB-01-003: Unknown invite_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{other_actor.id_}/trigger/reject-case-invite",
        json={"invite_id": "urn:uuid:nonexistent-invite"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# Tests for trigger/offer-case-participant-role
# ===========================================================================


@pytest.fixture
def target_actor(dl):
    """A second actor to receive the role offer."""
    target = as_Service(name="Target Actor")
    dl.create(target)
    return target


def test_trigger_offer_case_participant_role_returns_202(
    client_triggers, actor, case_obj, target_actor
):
    """POST /actors/{id}/trigger/offer-case-participant-role returns 202."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/offer-case-participant-role",
        json={
            "case_id": case_obj.id_,
            "target_actor_id": target_actor.id_,
            "role": "case_manager",
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_offer_case_participant_role_response_contains_activity(
    client_triggers, actor, case_obj, target_actor
):
    """Successful trigger response body contains 'activity' key with Offer type."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/offer-case-participant-role",
        json={
            "case_id": case_obj.id_,
            "target_actor_id": target_actor.id_,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None
    assert data["activity"]["type"] == "Offer"


def test_trigger_offer_case_participant_role_missing_required_fields_returns_422(
    client_triggers, actor
):
    """Missing case_id or target_actor_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/offer-case-participant-role",
        json={"role": "CASE_MANAGER"},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_offer_case_participant_role_unknown_actor_returns_404(
    client_triggers,
):
    """Unknown actor_id returns HTTP 404."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/offer-case-participant-role",
        json={
            "case_id": "urn:uuid:any-case",
            "target_actor_id": "urn:uuid:any-actor",
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


# ===========================================================================
# Tests for trigger/invite-actor-to-case
# ===========================================================================


@pytest.fixture
def client_triggers_invite(dl):
    """TestClient for invite-actor-to-case tests.

    Patches get_default_emitter with a no-op AsyncMock so outbox_handler
    completes without real HTTP delivery (which would block on retry backoff
    against a non-existent test host).
    """
    from unittest.mock import AsyncMock, patch

    app = FastAPI()
    app.include_router(trigger_actor_router.router)
    app.dependency_overrides[get_trigger_service] = lambda: TriggerService(
        dl, trigger_activity=TriggerActivityAdapter(dl)
    )
    app.dependency_overrides[get_trigger_dl] = lambda: dl
    app.dependency_overrides[get_canonical_actor_dl] = lambda: dl
    mock_emitter = AsyncMock()
    with patch(
        "vultron.adapters.driving.fastapi.outbox_handler.get_default_emitter",
        return_value=mock_emitter,
    ):
        yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def case_for_invite(dl, actor):
    """Case + Case Actor for invite-actor-to-case tests.

    Sets attributed_to=actor.id_ on the case so the BT can bootstrap the
    ledger chain (genesis hash derived from attributed_to — CLP-08-005).
    """
    case_actor = as_Service(name="Case Actor for Invite")
    dl.create(case_actor)
    case = as_VulnerabilityCase(
        name="TEST-CASE-INVITE",
        attributed_to=actor.id_,
    )
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
    # The Invite is authored as the CaseActor and committed to its ledger, so the
    # tree runs in the CaseActor's store — which needs the case for its genesis
    # anchor (CLP-08-001/002).
    seed_case_actor_replica(
        dl, case_actor.id_, case, owner_participant, case_manager_participant
    )
    case_actor_with_context = as_Service(
        id_=case_actor.id_,
        name="Case Actor for Invite",
        context=case.id_,
    )
    dl.save(case_actor_with_context)
    return case, case_actor


def test_trigger_invite_actor_to_case_returns_202(
    client_triggers_invite, actor, case_for_invite, other_actor
):
    """TB-01-002: POST /actors/{id}/trigger/invite-actor-to-case returns 202."""
    case, _ = case_for_invite
    resp = client_triggers_invite.post(
        f"/actors/{actor.id_}/trigger/invite-actor-to-case",
        json={"case_id": case.id_, "invitee_id": other_actor.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_invite_actor_to_case_response_contains_activity(
    client_triggers_invite, actor, case_for_invite, other_actor
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    case, _ = case_for_invite
    resp = client_triggers_invite.post(
        f"/actors/{actor.id_}/trigger/invite-actor-to-case",
        json={"case_id": case.id_, "invitee_id": other_actor.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None
    assert data["activity"]["type"] == "Invite"


def test_trigger_invite_actor_to_case_activity_actor_is_case_actor(
    client_triggers_invite, actor, case_for_invite, other_actor
):
    """Invite activity must be emitted from the Case Actor's identity (PCR-08-007).

    Also verifies that emitting_actor_id in the response matches the Case Actor,
    which is the value used to select the correct outbox for outbox_handler.
    """
    case, case_actor = case_for_invite
    resp = client_triggers_invite.post(
        f"/actors/{actor.id_}/trigger/invite-actor-to-case",
        json={"case_id": case.id_, "invitee_id": other_actor.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert data["activity"]["actor"] == case_actor.id_
    assert data["emitting_actor_id"] == case_actor.id_


def test_trigger_invite_actor_to_case_missing_case_id_returns_422(
    client_triggers_invite, actor, other_actor
):
    """TB-03-001: Missing case_id returns HTTP 422."""
    resp = client_triggers_invite.post(
        f"/actors/{actor.id_}/trigger/invite-actor-to-case",
        json={"invitee_id": other_actor.id_},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_invite_actor_to_case_missing_invitee_id_returns_422(
    client_triggers_invite, actor, case_for_invite
):
    """TB-03-001: Missing invitee_id returns HTTP 422."""
    case, _ = case_for_invite
    resp = client_triggers_invite.post(
        f"/actors/{actor.id_}/trigger/invite-actor-to-case",
        json={"case_id": case.id_},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_invite_actor_to_case_unknown_actor_returns_404(
    client_triggers_invite,
):
    """TB-01-003: Unknown actor_id returns HTTP 404."""
    resp = client_triggers_invite.post(
        "/actors/nonexistent-actor/trigger/invite-actor-to-case",
        json={
            "case_id": "urn:uuid:any-case",
            "invitee_id": "urn:uuid:any-invitee",
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_invite_actor_to_case_unknown_case_returns_404(
    client_triggers_invite, actor, other_actor
):
    """TB-01-003: Unknown case_id returns HTTP 404."""
    resp = client_triggers_invite.post(
        f"/actors/{actor.id_}/trigger/invite-actor-to-case",
        json={
            "case_id": "urn:uuid:nonexistent-case",
            "invitee_id": other_actor.id_,
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_invite_actor_to_case_unknown_invitee_is_accepted(
    client_triggers_invite, actor, case_for_invite
):
    """An invitee with no local record is invited by URI, not refused.

    This asserted HTTP 404, citing "TB-01-003" — an id that is not in the spec
    corpus at all (the TB topic covers pytest and ``pyproject.toml``), so the
    behaviour had no normative basis.

    A local record is not required: it was read and discarded, delivery derives
    the invitee's inbox from its URI alone, and under per-actor storage a peer's
    record lives in its own store (ADR-0072 decision 5) — so refusing meant
    refusing every cross-node invitee. The use case logs a WARNING instead, since
    actor discovery does not exist yet and the unverifiable invitee should not
    pass unremarked.
    """
    case, _ = case_for_invite
    resp = client_triggers_invite.post(
        f"/actors/{actor.id_}/trigger/invite-actor-to-case",
        json={
            "case_id": case.id_,
            "invitee_id": "urn:uuid:nonexistent-invitee",
        },
    )
    assert resp.status_code != status.HTTP_404_NOT_FOUND
    assert resp.status_code < 500, resp.text
