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
Tests for the propose-embargo-revision trigger endpoint
(POST /actors/{actor_id}/trigger/propose-embargo-revision).

Verifies TB-01 through TB-07 requirements from specs/triggerable-behaviors.yaml.
"""

import pytest
from fastapi import status
from unittest.mock import AsyncMock, patch

from vultron.core.states.em import EM

FUTURE_END_TIME = "2099-12-01T00:00:00Z"


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
# Tests for trigger/propose-embargo-revision
# ===========================================================================


def test_trigger_propose_embargo_revision_returns_202(
    client_triggers, actor, case_with_embargo
):
    """TB-01-002: POST /actors/{id}/trigger/propose-embargo-revision returns 202."""
    case_obj, _ = case_with_embargo
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo-revision",
        json={"case_id": case_obj.id_, "end_time": FUTURE_END_TIME},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_trigger_propose_embargo_revision_response_contains_activity_key(
    client_triggers, actor, case_with_embargo
):
    """TB-04-001: Successful trigger response body contains 'activity' key."""
    case_obj, _ = case_with_embargo
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo-revision",
        json={"case_id": case_obj.id_, "end_time": FUTURE_END_TIME},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "activity" in data
    assert data["activity"] is not None


def test_trigger_propose_embargo_revision_missing_case_id_returns_422(
    client_triggers, actor
):
    """TB-03-001: Request missing case_id returns HTTP 422."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo-revision",
        json={"end_time": FUTURE_END_TIME},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_propose_embargo_revision_missing_end_time_returns_422(
    client_triggers, actor, case_with_embargo
):
    """TB-03-001: Request missing end_time returns HTTP 422."""
    case_obj, _ = case_with_embargo
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo-revision",
        json={"case_id": case_obj.id_},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_trigger_propose_embargo_revision_unknown_actor_returns_404(
    client_triggers,
):
    """TB-01-003: Unknown actor_id returns HTTP 404 with structured body."""
    resp = client_triggers.post(
        "/actors/nonexistent-actor/trigger/propose-embargo-revision",
        json={"case_id": "urn:uuid:any-case", "end_time": FUTURE_END_TIME},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"]["error"] == "NotFound"


def test_trigger_propose_embargo_revision_unknown_case_returns_404(
    client_triggers, actor
):
    """TB-01-003: Unknown case_id returns HTTP 404."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo-revision",
        json={
            "case_id": "urn:uuid:nonexistent-case",
            "end_time": FUTURE_END_TIME,
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_propose_embargo_revision_non_active_em_state_returns_409(
    client_triggers, actor, case_without_participant
):
    """propose-embargo-revision returns 409 when case EM state is not ACTIVE/REVISE."""
    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo-revision",
        json={
            "case_id": case_without_participant.id_,
            "end_time": FUTURE_END_TIME,
        },
    )
    assert resp.status_code == status.HTTP_409_CONFLICT
    data = resp.json()
    assert data["detail"]["error"] == "Conflict"


def test_trigger_propose_embargo_revision_sets_em_state_to_revise(
    client_triggers, dl, actor, case_with_embargo
):
    """propose-embargo-revision transitions case EM state from ACTIVE to REVISE."""
    case_obj, _ = case_with_embargo

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo-revision",
        json={"case_id": case_obj.id_, "end_time": FUTURE_END_TIME},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    updated_case = dl.read(case_obj.id_)
    assert updated_case.current_status.em_state == EM.REVISE


def test_trigger_propose_embargo_revision_adds_activity_to_outbox(
    client_triggers, dl, actor, case_with_embargo
):
    """TB-07-001: Successful trigger adds a new activity to actor's outbox."""
    case_obj, _ = case_with_embargo
    outbox_before = set(dl.outbox_list())

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo-revision",
        json={"case_id": case_obj.id_, "end_time": FUTURE_END_TIME},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    outbox_after = set(dl.outbox_list())
    assert len(outbox_after - outbox_before) >= 1
