#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

# python
from fastapi import status
from fastapi.encoders import jsonable_encoder

from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRoles as CVDRole
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    CaseStatus,
    ParticipantStatus,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

_ACTOR_ID = "https://example.org/actors/alice"

# Use urn:uuid IDs for HTTP endpoint tests to avoid path-segment issues.
_HTTP_ACTOR_ID = "urn:uuid:aaaaaaaa-0000-0000-0000-000000000001"
_HTTP_CASE_ID = "urn:uuid:aaaaaaaa-0000-0000-0000-000000000003"
_HTTP_PARTICIPANT_ID = "urn:uuid:aaaaaaaa-0000-0000-0000-000000000004"


def test_created_actors_fixture_has_expected_count(created_actors):
    assert len(created_actors) == 6  # matches _actor_classes in conftest


def test_get_actors_list_returns_all_actors(client_actors, created_actors):
    resp = client_actors.get("/actors/")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == len(created_actors)


def test_get_actor_by_id_returns_actor_object(client_actors, created_actors):
    for actor in created_actors:
        resp = client_actors.get(f"/actors/{actor.as_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert isinstance(data, dict)
        assert "id" in data
        assert data["id"].endswith(actor.as_id)


def test_get_actor_not_found_returns_404(client_actors):
    resp = client_actors.get("/actors/nonexistent-actor-id")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_get_actor_inbox_returns_mailbox_structure(
    client_actors, created_actors
):
    for actor in created_actors:
        resp = client_actors.get(f"/actors/{actor.as_id}/inbox")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert isinstance(data, dict)
        assert "items" in data
        assert isinstance(data["items"], list)


def test_post_activity_to_actor_inbox_accepted(client_actors, created_actors):
    for actor in created_actors:
        note = as_Note(content="This is a test note.")
        activity = as_Create(as_object=note, actor=actor.as_id)
        payload = jsonable_encoder(activity, exclude_none=True)
        resp = client_actors.post(
            f"/actors/{actor.as_id}/inbox/", json=payload
        )
        assert resp.status_code == status.HTTP_202_ACCEPTED


def test_post_non_activity_to_actor_inbox_returns_422(
    client_actors, created_actors
):
    for actor in created_actors:
        note = as_Note(
            as_id="urn:uuid:test-note", content="This is a test note."
        )
        payload = jsonable_encoder(note, exclude_none=True)
        resp = client_actors.post(
            f"/actors/{actor.as_id}/inbox/", json=payload
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_get_actor_profile_returns_discovery_fields(
    client_actors, created_actors
):
    for actor in created_actors:
        resp = client_actors.get(f"/actors/{actor.as_id}/profile")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "id" in data
        assert data["id"].endswith(actor.as_id)
        assert "type" in data
        assert "inbox" in data
        assert "outbox" in data
        assert isinstance(data["inbox"], str), "inbox must be a URL string"
        assert isinstance(data["outbox"], str), "outbox must be a URL string"


def test_get_actor_profile_not_found_returns_404(client_actors):
    resp = client_actors.get("/actors/nonexistent-actor-id/profile")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_get_actors_does_not_log_raw_records_at_info_level(
    client_actors, created_actors, caplog
):
    import logging

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        resp = client_actors.get("/actors/")

    assert resp.status_code == status.HTTP_200_OK

    info_messages = [
        r.message for r in caplog.records if r.levelno == logging.INFO
    ]
    raw_dumps = [
        m for m in info_messages if m.startswith(("results:", "rec:"))
    ]
    assert (
        not raw_dumps
    ), f"Raw DB record dumps should not be logged at INFO level; found: {raw_dumps}"


def _seed_action_rules_data(dl):
    """Insert a minimal valid VulnerabilityCase / CaseParticipant pair."""
    case = VulnerabilityCase(
        as_id=_HTTP_CASE_ID,
        name="Test Case",
        actor_participant_index={_HTTP_ACTOR_ID: _HTTP_PARTICIPANT_ID},
        case_statuses=[CaseStatus(em_state=EM.ACTIVE, pxa_state=CS_pxa.Pxa)],
    )
    dl.create(case)

    participant = CaseParticipant(
        as_id=_HTTP_PARTICIPANT_ID,
        attributed_to=_HTTP_ACTOR_ID,
        context=_HTTP_CASE_ID,
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[
            ParticipantStatus(
                context=_HTTP_CASE_ID,
                rm_state=RM.ACCEPTED,
                vfd_state=CS_vfd.VFd,
            )
        ],
    )
    dl.create(participant)


def test_get_action_rules_returns_200_with_expected_fields(client_actors, dl):
    """Actor/case endpoint returns all required state and action fields."""
    _seed_action_rules_data(dl)

    resp = client_actors.get(
        f"/actors/{_HTTP_ACTOR_ID}/cases/{_HTTP_CASE_ID}/action-rules"
    )
    assert resp.status_code == status.HTTP_200_OK

    body = resp.json()
    expected_keys = {
        "participant_id",
        "participant_actor_id",
        "case_id",
        "role",
        "rm_state",
        "em_state",
        "vfd_state",
        "pxa_state",
        "cs_state",
        "actions",
    }
    assert expected_keys.issubset(body.keys())
    assert body["case_id"] == _HTTP_CASE_ID
    assert body["participant_id"] == _HTTP_PARTICIPANT_ID
    assert body["participant_actor_id"] == _HTTP_ACTOR_ID


def test_get_action_rules_case_not_found_returns_404(client_actors):
    """Missing case returns 404."""
    resp = client_actors.get(
        f"/actors/{_HTTP_ACTOR_ID}/cases/"
        "urn:uuid:00000000-0000-0000-0000-000000000000/action-rules"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_get_action_rules_actor_not_in_case_returns_404(client_actors, dl):
    """Actor outside the selected case returns 404."""
    _seed_action_rules_data(dl)

    resp = client_actors.get(
        "/actors/urn:uuid:99999999-0000-0000-0000-000000000000/cases/"
        f"{_HTTP_CASE_ID}/action-rules"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
