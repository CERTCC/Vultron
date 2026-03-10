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
Tests for the embargo trigger endpoints
(POST /actors/{actor_id}/trigger/{propose,evaluate,terminate}-embargo).

Verifies TB-01 through TB-07 requirements from specs/triggerable-behaviors.md.
"""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from vultron.api.v2.data.actor_io import init_actor_io
from vultron.api.v2.datalayer.db_record import object_to_record
from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
from vultron.api.v2.routers import trigger_embargo as trigger_embargo_router
from vultron.wire.as2.vocab.activities.embargo import EmProposeEmbargo
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.bt.embargo_management.states import EM

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dl(datalayer):
    return datalayer


@pytest.fixture
def client_triggers(dl):
    app = FastAPI()
    app.include_router(trigger_embargo_router.router)
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
def case_without_participant(dl):
    """Create a VulnerabilityCase with no CaseParticipant for the actor."""
    case_obj = VulnerabilityCase(name="TEST-CASE-NO-PARTICIPANT")
    dl.create(case_obj)
    return case_obj


@pytest.fixture
def case_with_embargo(dl, actor):
    """A VulnerabilityCase with an active EmbargoEvent."""
    case_obj = VulnerabilityCase(name="EMBARGO-CASE-001")
    embargo = EmbargoEvent(context=case_obj.as_id)
    dl.create(embargo)
    case_obj.set_embargo(embargo.as_id)
    dl.create(case_obj)
    return case_obj, embargo


@pytest.fixture
def case_with_proposal(dl, actor):
    """A VulnerabilityCase with a pending EmProposeEmbargo in EM.PROPOSED state."""
    case_obj = VulnerabilityCase(name="PROPOSAL-CASE-001")
    embargo = EmbargoEvent(context=case_obj.as_id)
    dl.create(embargo)
    proposal = EmProposeEmbargo(
        actor=actor.as_id,
        object=embargo.as_id,
        context=case_obj.as_id,
    )
    dl.create(proposal)
    case_obj.current_status.em_state = EM.PROPOSED
    case_obj.proposed_embargoes.append(embargo.as_id)
    dl.create(case_obj)
    return case_obj, proposal, embargo


# ===========================================================================
# Tests for trigger/propose-embargo
# ===========================================================================


def test_trigger_propose_embargo_returns_202(
    client_triggers, actor, case_without_participant
):
    """TB-01-002: POST /actors/{id}/trigger/propose-embargo returns HTTP 202."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/propose-embargo",
        json={"case_id": case_without_participant.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_propose_embargo_response_contains_activity_key(
    client_triggers, actor, case_without_participant
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/propose-embargo",
        json={"case_id": case_without_participant.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_propose_embargo_missing_case_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/propose-embargo",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_trigger_propose_embargo_ignores_unknown_fields(
    client_triggers, actor, case_without_participant
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/propose-embargo",
        json={"case_id": case_without_participant.as_id, "unknown_xyz": 99},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_propose_embargo_unknown_actor_returns_404(client_triggers):
    """TB-01-003: Unknown actor_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/propose-embargo",
        json={"case_id": "urn:uuid:any-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_propose_embargo_unknown_case_returns_404(
    client_triggers, actor
):
    """TB-01-003: Unknown case_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/propose-embargo",
        json={"case_id": "urn:uuid:nonexistent-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_propose_embargo_adds_activity_to_outbox(
    client_triggers, dl, actor, case_without_participant
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    actor_before = dl.read(actor.as_id)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/propose-embargo",
        json={"case_id": case_without_participant.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.as_id)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_propose_embargo_updates_em_state_to_proposed(
    client_triggers, dl, actor, case_without_participant
):
    """propose-embargo transitions case EM state from N to P."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/propose-embargo",
        json={"case_id": case_without_participant.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_without_participant.as_id)
    assert updated_case.current_status.em_state == EM.PROPOSED


def test_trigger_propose_embargo_from_active_updates_em_state_to_revise(
    client_triggers, dl, actor, case_with_embargo
):
    """propose-embargo transitions case EM state from A to R when embargo is active."""
    case_obj, _ = case_with_embargo

    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/propose-embargo",
        json={"case_id": case_obj.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.as_id)
    assert updated_case.current_status.em_state == EM.REVISE


def test_trigger_propose_embargo_exited_returns_409(
    client_triggers, dl, actor, case_without_participant
):
    """propose-embargo returns HTTP 409 when EM state is EXITED."""
    case_obj = dl.read(case_without_participant.as_id)
    case_obj.current_status.em_state = EM.EXITED
    dl.update(case_obj.as_id, object_to_record(case_obj))

    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/propose-embargo",
        json={"case_id": case_without_participant.as_id},
    )
    assert resp.status_code == status.HTTP_409_CONFLICT
    data = resp.json()
    assert data["detail"]["error"] == "Conflict"


# ===========================================================================
# Tests for trigger/evaluate-embargo
# ===========================================================================


def test_trigger_evaluate_embargo_returns_202(
    client_triggers, actor, case_with_proposal
):
    """TB-01-002: POST /actors/{id}/trigger/evaluate-embargo returns HTTP 202."""
    case_obj, proposal, _ = case_with_proposal
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/evaluate-embargo",
        json={"case_id": case_obj.as_id, "proposal_id": proposal.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_evaluate_embargo_response_contains_activity_key(
    client_triggers, actor, case_with_proposal
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    case_obj, proposal, _ = case_with_proposal
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/evaluate-embargo",
        json={"case_id": case_obj.as_id, "proposal_id": proposal.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_evaluate_embargo_missing_case_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/evaluate-embargo",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_trigger_evaluate_embargo_ignores_unknown_fields(
    client_triggers, actor, case_with_proposal
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    case_obj, proposal, _ = case_with_proposal
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/evaluate-embargo",
        json={
            "case_id": case_obj.as_id,
            "proposal_id": proposal.as_id,
            "extra": "ignored",
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_evaluate_embargo_unknown_actor_returns_404(client_triggers):
    """TB-01-003: Unknown actor_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/evaluate-embargo",
        json={"case_id": "urn:uuid:any-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_evaluate_embargo_unknown_case_returns_404(
    client_triggers, actor
):
    """TB-01-003: Unknown case_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/evaluate-embargo",
        json={"case_id": "urn:uuid:nonexistent-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_evaluate_embargo_unknown_proposal_returns_404(
    client_triggers, actor, case_without_participant
):
    """TB-01-003: Unknown proposal_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/evaluate-embargo",
        json={
            "case_id": case_without_participant.as_id,
            "proposal_id": "urn:uuid:nonexistent-proposal",
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_evaluate_embargo_no_proposal_returns_404(
    client_triggers, actor, case_without_participant
):
    """evaluate-embargo returns HTTP 404 when no proposal is found for the case."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/evaluate-embargo",
        json={"case_id": case_without_participant.as_id},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_evaluate_embargo_adds_activity_to_outbox(
    client_triggers, dl, actor, case_with_proposal
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    case_obj, proposal, _ = case_with_proposal
    actor_before = dl.read(actor.as_id)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/evaluate-embargo",
        json={"case_id": case_obj.as_id, "proposal_id": proposal.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.as_id)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_evaluate_embargo_activates_embargo(
    client_triggers, dl, actor, case_with_proposal
):
    """evaluate-embargo activates the embargo and sets EM state to ACTIVE."""
    case_obj, proposal, embargo = case_with_proposal

    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/evaluate-embargo",
        json={"case_id": case_obj.as_id, "proposal_id": proposal.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.as_id)
    assert updated_case.current_status.em_state == EM.ACTIVE
    assert updated_case.active_embargo is not None


def test_trigger_evaluate_embargo_without_proposal_id_uses_first_proposal(
    client_triggers, dl, actor, case_with_proposal
):
    """evaluate-embargo without proposal_id finds the first pending proposal."""
    case_obj, _, _ = case_with_proposal

    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/evaluate-embargo",
        json={"case_id": case_obj.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.as_id)
    assert updated_case.current_status.em_state == EM.ACTIVE


# ===========================================================================
# Tests for trigger/terminate-embargo
# ===========================================================================


def test_trigger_terminate_embargo_returns_202(
    client_triggers, actor, case_with_embargo
):
    """TB-01-002: POST /actors/{id}/trigger/terminate-embargo returns HTTP 202."""
    case_obj, _ = case_with_embargo
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/terminate-embargo",
        json={"case_id": case_obj.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_terminate_embargo_response_contains_activity_key(
    client_triggers, actor, case_with_embargo
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    case_obj, _ = case_with_embargo
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/terminate-embargo",
        json={"case_id": case_obj.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_terminate_embargo_missing_case_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/terminate-embargo",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_trigger_terminate_embargo_ignores_unknown_fields(
    client_triggers, actor, case_with_embargo
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    case_obj, _ = case_with_embargo
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/terminate-embargo",
        json={"case_id": case_obj.as_id, "extra": "ignored"},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_terminate_embargo_unknown_actor_returns_404(client_triggers):
    """TB-01-003: Unknown actor_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/terminate-embargo",
        json={"case_id": "urn:uuid:any-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_terminate_embargo_unknown_case_returns_404(
    client_triggers, actor
):
    """TB-01-003: Unknown case_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/terminate-embargo",
        json={"case_id": "urn:uuid:nonexistent-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_terminate_embargo_no_active_embargo_returns_409(
    client_triggers, actor, case_without_participant
):
    """terminate-embargo returns HTTP 409 when case has no active embargo."""
    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/terminate-embargo",
        json={"case_id": case_without_participant.as_id},
    )
    assert resp.status_code == status.HTTP_409_CONFLICT
    data = resp.json()
    assert data["detail"]["error"] == "Conflict"


def test_trigger_terminate_embargo_adds_activity_to_outbox(
    client_triggers, dl, actor, case_with_embargo
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    case_obj, _ = case_with_embargo
    actor_before = dl.read(actor.as_id)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/terminate-embargo",
        json={"case_id": case_obj.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.as_id)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_terminate_embargo_updates_em_state_to_exited(
    client_triggers, dl, actor, case_with_embargo
):
    """terminate-embargo transitions case EM state to EXITED."""
    case_obj, _ = case_with_embargo

    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/terminate-embargo",
        json={"case_id": case_obj.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.as_id)
    assert updated_case.current_status.em_state == EM.EXITED


def test_trigger_terminate_embargo_clears_active_embargo(
    client_triggers, dl, actor, case_with_embargo
):
    """terminate-embargo clears the active_embargo field on the case."""
    case_obj, _ = case_with_embargo

    resp = client_triggers.post(
        f"/actors/{actor.as_id}/trigger/terminate-embargo",
        json={"case_id": case_obj.as_id},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.as_id)
    assert updated_case.active_embargo is None
