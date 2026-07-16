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
Tests for the propose-embargo trigger endpoint
(POST /actors/{actor_id}/trigger/propose-embargo).

Verifies TB-01 through TB-07 requirements from specs/triggerable-behaviors.yaml.
"""

import pytest
from fastapi import status
from unittest.mock import AsyncMock, patch

from vultron.adapters.driven.db_record import object_to_record
from vultron.core.states.em import EM

FUTURE_END_TIME = "2099-12-01T00:00:00Z"


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

    The test ``test_propose_embargo_schedules_outbox_handler`` uses
    ``unittest.mock.patch`` as a context manager inside the test body, which
    overrides this fixture's patch for the duration of that context.
    """
    with patch(
        "vultron.adapters.driving.fastapi.routers"
        ".trigger_embargo.outbox_handler",
        new_callable=AsyncMock,
    ):
        yield


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
    outbox_before = set(dl.outbox_list())

    resp = client_triggers.post(
        f"/actors/{actor.id_}/trigger/propose-embargo",
        json={
            "case_id": case_without_participant.id_,
            "end_time": FUTURE_END_TIME,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED

    outbox_after = set(dl.outbox_list())
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


def test_propose_embargo_schedules_outbox_handler(
    client_triggers, dl, actor, case_without_participant
):
    """D5-6-TRIGDELIV: propose-embargo schedules outbox delivery after execution."""
    with patch(
        "vultron.adapters.driving.fastapi.routers"
        ".trigger_embargo.outbox_handler",
        new_callable=AsyncMock,
    ) as mock_outbox:
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
    assert mock_outbox.call_args.args[1] is dl
    assert mock_outbox.call_args.args[2] is dl
