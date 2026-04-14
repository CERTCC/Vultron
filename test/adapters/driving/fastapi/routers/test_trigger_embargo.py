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

from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.routers.trigger_embargo import _actor_dl
from vultron.adapters.driving.fastapi.routers import (
    trigger_embargo as trigger_embargo_router,
)
from vultron.wire.as2.vocab.activities.embargo import EmProposeEmbargoActivity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.core.states.em import EM

FUTURE_END_TIME = "2099-12-01T00:00:00Z"

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
    app.include_router(trigger_embargo_router.router)
    app.dependency_overrides[_actor_dl] = lambda: dl
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


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
    embargo = EmbargoEvent(context=case_obj.id_)
    dl.create(embargo)
    case_obj.set_embargo(embargo.id_)
    case_obj.current_status.em_state = EM.ACTIVE
    dl.create(case_obj)
    return case_obj, embargo


@pytest.fixture
def case_with_proposal(dl, actor):
    """A VulnerabilityCase with a pending EmProposeEmbargoActivity in EM.PROPOSED state."""
    case_obj = VulnerabilityCase(name="PROPOSAL-CASE-001")
    embargo = EmbargoEvent(context=case_obj.id_)
    dl.create(embargo)
    proposal = EmProposeEmbargoActivity(
        actor=actor.id_,
        object_=embargo.id_,
        context=case_obj.id_,
    )
    dl.create(proposal)
    case_obj.current_status.em_state = EM.PROPOSED
    case_obj.proposed_embargoes.append(embargo.id_)
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
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={
            "case_id": case_without_participant.id_,
            "end_time": FUTURE_END_TIME,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_propose_embargo_response_contains_activity_key(
    client_triggers, actor, case_without_participant
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={
            "case_id": case_without_participant.id_,
            "end_time": FUTURE_END_TIME,
        },
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
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={"end_time": FUTURE_END_TIME},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_propose_embargo_missing_end_time_returns_422(
    client_triggers, actor, case_without_participant
):
    """propose-embargo without end_time returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={"case_id": case_without_participant.id_},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_propose_embargo_naive_end_time_returns_422(
    client_triggers, actor, case_without_participant
):
    """propose-embargo with timezone-naive end_time returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={
            "case_id": case_without_participant.id_,
            "end_time": "2099-12-01T00:00:00",
        },
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_propose_embargo_past_end_time_returns_422(
    client_triggers, actor, case_without_participant
):
    """propose-embargo with a past end_time returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={
            "case_id": case_without_participant.id_,
            "end_time": "2020-01-01T00:00:00Z",
        },
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_propose_embargo_ignores_unknown_fields(
    client_triggers, actor, case_without_participant
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={
            "case_id": case_without_participant.id_,
            "end_time": FUTURE_END_TIME,
            "unknown_xyz": 99,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_propose_embargo_unknown_actor_returns_404(client_triggers):
    """TB-01-003: Unknown actor_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/propose-embargo",
        json={"case_id": "urn:uuid:any-case", "end_time": FUTURE_END_TIME},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_propose_embargo_unknown_case_returns_404(
    client_triggers, actor
):
    """TB-01-003: Unknown case_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={
            "case_id": "urn:uuid:nonexistent-case",
            "end_time": FUTURE_END_TIME,
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_propose_embargo_invalid_case_id_returns_422(
    client_triggers, actor
):
    """propose-embargo with a non-URI case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={"case_id": "not-a-uri", "end_time": FUTURE_END_TIME},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_propose_embargo_adds_activity_to_outbox(
    client_triggers, dl, actor, case_without_participant
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    actor_before = dl.read(actor.id_)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={
            "case_id": case_without_participant.id_,
            "end_time": FUTURE_END_TIME,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.id_)
    outbox_after = set(
        item for item in actor_after.outbox.items if isinstance(item, str)
    )
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_propose_embargo_updates_em_state_to_proposed(
    client_triggers, dl, actor, case_without_participant
):
    """propose-embargo transitions case EM state from N to P."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={
            "case_id": case_without_participant.id_,
            "end_time": FUTURE_END_TIME,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_without_participant.id_)
    assert updated_case.current_status.em_state == EM.PROPOSED


def test_trigger_propose_embargo_from_active_updates_em_state_to_revise(
    client_triggers, dl, actor, case_with_embargo
):
    """propose-embargo transitions case EM state from A to R when embargo is active."""
    case_obj, _ = case_with_embargo

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={"case_id": case_obj.id_, "end_time": FUTURE_END_TIME},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.id_)
    assert updated_case.current_status.em_state == EM.REVISE


def test_trigger_propose_embargo_exited_returns_409(
    client_triggers, dl, actor, case_without_participant
):
    """propose-embargo returns HTTP 409 when EM state is EXITED."""
    case_obj = dl.read(case_without_participant.id_)
    case_obj.current_status.em_state = EM.EXITED
    dl.update(case_obj.id_, object_to_record(case_obj))

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={
            "case_id": case_without_participant.id_,
            "end_time": FUTURE_END_TIME,
        },
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
        f"/actors/{actor.id_}/trigger/evaluate-embargo",
        json={"case_id": case_obj.id_, "proposal_id": proposal.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_evaluate_embargo_response_contains_activity_key(
    client_triggers, actor, case_with_proposal
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    case_obj, proposal, _ = case_with_proposal
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/evaluate-embargo",
        json={"case_id": case_obj.id_, "proposal_id": proposal.id_},
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
        f"/actors/{actor.id_}/trigger/evaluate-embargo",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_evaluate_embargo_ignores_unknown_fields(
    client_triggers, actor, case_with_proposal
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    case_obj, proposal, _ = case_with_proposal
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/evaluate-embargo",
        json={
            "case_id": case_obj.id_,
            "proposal_id": proposal.id_,
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
        f"/actors/{actor.id_}/trigger/evaluate-embargo",
        json={"case_id": "urn:uuid:nonexistent-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_evaluate_embargo_unknown_proposal_returns_404(
    client_triggers, actor, case_without_participant
):
    """TB-01-003: Unknown proposal_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/evaluate-embargo",
        json={
            "case_id": case_without_participant.id_,
            "proposal_id": "urn:uuid:nonexistent-proposal",
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_evaluate_embargo_no_proposal_returns_404(
    client_triggers, actor, case_without_participant
):
    """evaluate-embargo returns HTTP 404 when no proposal is found for the case."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/evaluate-embargo",
        json={"case_id": case_without_participant.id_},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_evaluate_embargo_adds_activity_to_outbox(
    client_triggers, dl, actor, case_with_proposal
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    case_obj, proposal, _ = case_with_proposal
    actor_before = dl.read(actor.id_)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/evaluate-embargo",
        json={"case_id": case_obj.id_, "proposal_id": proposal.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.id_)
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
        f"/actors/{actor.id_}/trigger/evaluate-embargo",
        json={"case_id": case_obj.id_, "proposal_id": proposal.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.id_)
    assert updated_case.current_status.em_state == EM.ACTIVE
    assert updated_case.active_embargo is not None


def test_trigger_evaluate_embargo_without_proposal_id_uses_first_proposal(
    client_triggers, dl, actor, case_with_proposal
):
    """evaluate-embargo without proposal_id finds the first pending proposal."""
    case_obj, _, _ = case_with_proposal

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/evaluate-embargo",
        json={"case_id": case_obj.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.id_)
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
        f"/actors/{actor.id_}/trigger/terminate-embargo",
        json={"case_id": case_obj.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_terminate_embargo_response_contains_activity_key(
    client_triggers, actor, case_with_embargo
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    case_obj, _ = case_with_embargo
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/terminate-embargo",
        json={"case_id": case_obj.id_},
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
        f"/actors/{actor.id_}/trigger/terminate-embargo",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_terminate_embargo_ignores_unknown_fields(
    client_triggers, actor, case_with_embargo
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    case_obj, _ = case_with_embargo
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/terminate-embargo",
        json={"case_id": case_obj.id_, "extra": "ignored"},
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
        f"/actors/{actor.id_}/trigger/terminate-embargo",
        json={"case_id": "urn:uuid:nonexistent-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_terminate_embargo_no_active_embargo_returns_409(
    client_triggers, actor, case_without_participant
):
    """terminate-embargo returns HTTP 409 when case has no active embargo."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/terminate-embargo",
        json={"case_id": case_without_participant.id_},
    )
    assert resp.status_code == status.HTTP_409_CONFLICT
    data = resp.json()
    assert data["detail"]["error"] == "Conflict"


def test_trigger_terminate_embargo_adds_activity_to_outbox(
    client_triggers, dl, actor, case_with_embargo
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    case_obj, _ = case_with_embargo
    actor_before = dl.read(actor.id_)
    outbox_before = set(
        item for item in actor_before.outbox.items if isinstance(item, str)
    )

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/terminate-embargo",
        json={"case_id": case_obj.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    actor_after = dl.read(actor.id_)
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
        f"/actors/{actor.id_}/trigger/terminate-embargo",
        json={"case_id": case_obj.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.id_)
    assert updated_case.current_status.em_state == EM.EXITED


def test_trigger_terminate_embargo_clears_active_embargo(
    client_triggers, dl, actor, case_with_embargo
):
    """terminate-embargo clears the active_embargo field on the case."""
    case_obj, _ = case_with_embargo

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/terminate-embargo",
        json={"case_id": case_obj.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.id_)
    assert updated_case.active_embargo is None


def test_trigger_terminate_embargo_invalid_em_state_returns_409(
    client_triggers, dl, actor, case_with_embargo
):
    """terminate-embargo returns HTTP 409 when EM state is not ACTIVE or REVISE.

    Guards against bypassing the EM machine: even if active_embargo is set,
    terminating from a state with no TERMINATE transition (e.g. PROPOSED) must
    be rejected.
    """
    case_obj, _ = case_with_embargo
    stored = dl.read(case_obj.id_)
    stored.current_status.em_state = EM.PROPOSED
    dl.update(stored.id_, object_to_record(stored))

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/terminate-embargo",
        json={"case_id": case_obj.id_},
    )
    assert resp.status_code == status.HTTP_409_CONFLICT
    data = resp.json()
    assert data["detail"]["error"] == "Conflict"


# ===========================================================================
# Tests for outbox delivery scheduling (D5-6-TRIGDELIV)
# ===========================================================================


class TestTriggerEmbargoOutboxScheduling:
    """D5-6-TRIGDELIV: embargo trigger endpoints must schedule outbox_handler."""

    def test_propose_embargo_schedules_outbox_handler(
        self, client_triggers, actor, case_without_participant
    ):
        """propose-embargo schedules outbox delivery after execution."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_dl = MagicMock()
        with patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_embargo.outbox_handler",
            new_callable=AsyncMock,
        ) as mock_outbox, patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_embargo.get_datalayer",
            return_value=mock_dl,
        ):
            resp = client_triggers.post(
                f"/actors/{actor.id_}/trigger/propose-embargo",
                json={
                    "case_id": case_without_participant.id_,
                    "end_time": FUTURE_END_TIME,
                },
            )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        mock_outbox.assert_called_once()
        assert mock_outbox.call_args.args[0] == actor.id_
        assert mock_outbox.call_args.args[1] is mock_dl

    def test_evaluate_embargo_schedules_outbox_handler(
        self, client_triggers, actor, case_with_proposal
    ):
        """evaluate-embargo schedules outbox delivery after execution."""
        from unittest.mock import AsyncMock, MagicMock, patch

        case_obj, proposal, _ = case_with_proposal
        mock_dl = MagicMock()
        with patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_embargo.outbox_handler",
            new_callable=AsyncMock,
        ) as mock_outbox, patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_embargo.get_datalayer",
            return_value=mock_dl,
        ):
            resp = client_triggers.post(
                f"/actors/{actor.id_}/trigger/evaluate-embargo",
                json={
                    "case_id": case_obj.id_,
                    "proposal_id": proposal.id_,
                },
            )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        mock_outbox.assert_called_once()
        assert mock_outbox.call_args.args[0] == actor.id_

    def test_terminate_embargo_schedules_outbox_handler(
        self, client_triggers, actor, case_with_embargo
    ):
        """terminate-embargo schedules outbox delivery after execution."""
        from unittest.mock import AsyncMock, MagicMock, patch

        case_obj, _ = case_with_embargo
        mock_dl = MagicMock()
        with patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_embargo.outbox_handler",
            new_callable=AsyncMock,
        ) as mock_outbox, patch(
            "vultron.adapters.driving.fastapi.routers"
            ".trigger_embargo.get_datalayer",
            return_value=mock_dl,
        ):
            resp = client_triggers.post(
                f"/actors/{actor.id_}/trigger/terminate-embargo",
                json={"case_id": case_obj.id_},
            )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        mock_outbox.assert_called_once()
        assert mock_outbox.call_args.args[0] == actor.id_
