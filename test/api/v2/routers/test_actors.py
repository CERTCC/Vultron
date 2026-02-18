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

from vultron.as_vocab.base.objects.activities.transitive import as_Create
from vultron.as_vocab.base.objects.object_types import as_Note


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
        activity = as_Create(object=note, actor=actor.as_id)
        payload = jsonable_encoder(activity, exclude_none=True)
        resp = client_actors.post(
            f"/actors/{actor.as_id}/inbox/", json=payload
        )
        assert resp.status_code == status.HTTP_202_ACCEPTED


def test_post_non_activity_to_actor_inbox_returns_422(
    client_actors, created_actors
):
    for actor in created_actors:
        note = as_Note(id="urn:uuid:test-note", content="This is a test note.")
        payload = jsonable_encoder(note, exclude_none=True)
        resp = client_actors.post(
            f"/actors/{actor.as_id}/inbox/", json=payload
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
