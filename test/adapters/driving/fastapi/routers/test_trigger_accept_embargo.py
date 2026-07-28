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
Tests for the accept-embargo trigger endpoint
(POST /actors/{actor_id}/trigger/accept-embargo).

Verifies TB-01 through TB-07 requirements from specs/triggerable-behaviors.yaml.
"""

import pytest
from fastapi import status
from unittest.mock import AsyncMock, patch

from vultron.core.states.em import EM

# ---------------------------------------------------------------------------
# Module-level fixture: suppress outbox delivery retries
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_outbox_delivery():
    """Suppress real outbox delivery for every test in this module."""
    with patch(
        "vultron.adapters.driving.fastapi.routers"
        ".trigger_embargo.outbox_handler",
        new_callable=AsyncMock,
    ):
        yield


# ===========================================================================
# Tests for trigger/accept-embargo
# ===========================================================================


def test_trigger_accept_embargo_returns_202(
    client_triggers, actor, case_with_proposal
):
    """TB-01-002: POST /actors/{id}/trigger/accept-embargo returns HTTP 202."""
    case_obj, proposal, _ = case_with_proposal
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/accept-embargo",
        json={"case_id": case_obj.id_, "proposal_id": proposal.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_accept_embargo_response_contains_activity_key(
    client_triggers, actor, case_with_proposal
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    case_obj, proposal, _ = case_with_proposal
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/accept-embargo",
        json={"case_id": case_obj.id_, "proposal_id": proposal.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_accept_embargo_object_is_proposal(
    client_triggers, actor, case_with_proposal
):
    """DR-05: Accept activity object_ must be the original proposal, not the embargo event."""
    case_obj, proposal, _ = case_with_proposal
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/accept-embargo",
        json={"case_id": case_obj.id_, "proposal_id": proposal.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert data["activity"]["object"]["id"] == proposal.id_


def test_trigger_accept_embargo_missing_case_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/accept-embargo",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_accept_embargo_ignores_unknown_fields(
    client_triggers, actor, case_with_proposal
):
    """TB-03-002: Unknown fields in request body are silently ignored."""
    case_obj, proposal, _ = case_with_proposal
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/accept-embargo",
        json={
            "case_id": case_obj.id_,
            "proposal_id": proposal.id_,
            "extra": "ignored",
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_accept_embargo_unknown_actor_returns_404(client_triggers):
    """TB-01-003: Unknown actor_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/accept-embargo",
        json={"case_id": "urn:uuid:any-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_accept_embargo_unknown_case_returns_404(
    client_triggers, actor
):
    """TB-01-003: Unknown case_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/accept-embargo",
        json={"case_id": "urn:uuid:nonexistent-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_accept_embargo_unknown_proposal_returns_404(
    client_triggers, actor, case_without_participant
):
    """TB-01-003: Unknown proposal_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/accept-embargo",
        json={
            "case_id": case_without_participant.id_,
            "proposal_id": "urn:uuid:nonexistent-proposal",
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_accept_embargo_no_proposal_returns_404(
    client_triggers, actor, case_without_participant
):
    """accept-embargo returns HTTP 404 when no proposal is found for the case."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/accept-embargo",
        json={"case_id": case_without_participant.id_},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_accept_embargo_adds_activity_to_outbox(
    client_triggers, dl, actor, case_with_proposal
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    case_obj, proposal, _ = case_with_proposal
    outbox_before = set(dl.outbox_list())

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/accept-embargo",
        json={"case_id": case_obj.id_, "proposal_id": proposal.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    outbox_after = set(dl.outbox_list())
    assert len(outbox_after - outbox_before) >= 1


def test_trigger_accept_embargo_activates_embargo(
    client_triggers, dl, actor, case_with_proposal
):
    """accept-embargo activates the embargo and sets EM state to ACTIVE."""
    case_obj, proposal, embargo = case_with_proposal

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/accept-embargo",
        json={"case_id": case_obj.id_, "proposal_id": proposal.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.id_)
    assert updated_case.current_status.em.state == EM.ACTIVE
    assert updated_case.active_embargo is not None


def test_trigger_accept_embargo_without_proposal_id_uses_first_proposal(
    client_triggers, dl, actor, case_with_proposal
):
    """accept-embargo without proposal_id finds the first pending proposal."""
    case_obj, _, _ = case_with_proposal

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/accept-embargo",
        json={"case_id": case_obj.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.id_)
    assert updated_case.current_status.em.state == EM.ACTIVE


def test_accept_embargo_schedules_outbox_handler(
    client_triggers, dl, actor, case_with_proposal
):
    """D5-6-TRIGDELIV: accept-embargo schedules outbox delivery after execution."""
    case_obj, proposal, _ = case_with_proposal
    with patch(
        "vultron.adapters.driving.fastapi.routers"
        ".trigger_embargo.outbox_handler",
        new_callable=AsyncMock,
    ) as mock_outbox:
        resp = client_triggers.post(
            f"/actors/{actor.id_}/trigger/accept-embargo",
            json={
                "case_id": case_obj.id_,
                "proposal_id": proposal.id_,
            },
        )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    mock_outbox.assert_called_once()
    assert mock_outbox.call_args.args[0] == actor.id_
    assert mock_outbox.call_args.args[1] is dl
    assert mock_outbox.call_args.args[2] is dl
