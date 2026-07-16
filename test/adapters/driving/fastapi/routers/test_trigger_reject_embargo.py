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
Tests for the reject-embargo trigger endpoint
(POST /actors/{actor_id}/trigger/reject-embargo).

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
# Tests for trigger/reject-embargo
# ===========================================================================


def test_trigger_reject_embargo_returns_202(
    client_triggers, actor, case_with_proposal
):
    """TB-01-002: POST /actors/{id}/trigger/reject-embargo returns HTTP 202."""
    case_obj, proposal, _ = case_with_proposal
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-embargo",
        json={"case_id": case_obj.id_, "proposal_id": proposal.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_reject_embargo_response_contains_activity_key(
    client_triggers, actor, case_with_proposal
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    case_obj, proposal, _ = case_with_proposal
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-embargo",
        json={"case_id": case_obj.id_, "proposal_id": proposal.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_reject_embargo_missing_case_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-embargo",
        json={},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_reject_embargo_unknown_actor_returns_404(client_triggers):
    """TB-01-003: Unknown actor_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/reject-embargo",
        json={"case_id": "urn:uuid:any-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_reject_embargo_unknown_case_returns_404(
    client_triggers, actor
):
    """TB-01-003: Unknown case_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-embargo",
        json={"case_id": "urn:uuid:nonexistent-case"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_reject_embargo_no_proposal_returns_404(
    client_triggers, actor, case_without_participant
):
    """reject-embargo returns HTTP 404 when no proposal is found for the case."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-embargo",
        json={"case_id": case_without_participant.id_},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_reject_embargo_sets_em_state_to_no_embargo(
    client_triggers, dl, actor, case_with_proposal
):
    """reject-embargo transitions case EM state from PROPOSED to NO_EMBARGO."""
    case_obj, proposal, _ = case_with_proposal

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-embargo",
        json={"case_id": case_obj.id_, "proposal_id": proposal.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.id_)
    assert updated_case.current_status.em_state == EM.NO_EMBARGO


def test_trigger_reject_embargo_adds_activity_to_outbox(
    client_triggers, dl, actor, case_with_proposal
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    case_obj, proposal, _ = case_with_proposal
    outbox_before = set(dl.outbox_list())

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/reject-embargo",
        json={"case_id": case_obj.id_, "proposal_id": proposal.id_},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    outbox_after = set(dl.outbox_list())
    assert len(outbox_after - outbox_before) >= 1
