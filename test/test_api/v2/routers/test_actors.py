#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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
import unittest

from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from vultron.api.v2.routers import actors as actors_module
from vultron.as_vocab.base.objects.activities.transitive import as_Create
from vultron.as_vocab.base.objects.object_types import as_Note


class ActorsRouterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a small FastAPI app that includes the router under test
        app = FastAPI()
        app.include_router(actors_module.router)
        cls.client = TestClient(app)

    def _get_id_from_url(self, url: str) -> str:
        # an actor id is typically the last segment of the URL
        return url.rstrip("/").split("/")[-1]

    def _get_first_actor_id(self) -> str:
        resp = self.client.get("/actors/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        first = data[0]
        # common ActivityStreams actor id key is "id"
        actor_id = (
            first.get("id")
            or first.get("url")
            or first.get("actor")
            or first.get("actor_id")
        )
        self.assertIsNotNone(actor_id)

        return self._get_id_from_url(actor_id)

    def test_get_actors_list(self):
        resp = self.client.get("/actors/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIsInstance(data, list)
        # registry registers example actors at import time
        self.assertGreaterEqual(len(data), 1)

    def test_get_actor_by_id(self):
        actor_id = self._get_first_actor_id()
        resp = self.client.get(f"/actors/{actor_id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIsInstance(data, dict)
        self.assertIn("id", data)
        # if the id is a URL, ensure it ends with the actor_id
        self.assertTrue(data["id"].endswith(actor_id))

    def test_get_actor_not_found(self):
        resp = self.client.get("/actors/nonexistent-actor-id")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_actor_inbox(self):
        actor_id = self._get_first_actor_id()
        resp = self.client.get(f"/actors/{actor_id}/inbox")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIsInstance(data, dict)
        self.assertIn("items", data)
        self.assertIsInstance(data["items"], list)

    def test_post_actor_inbox_accepted(self):
        actor_id = self._get_first_actor_id()

        note = as_Note(
            id="urn:uuid:test-note",
            content="This is a test note.",
        )
        activity = as_Create(
            id="urn:uuid:test-create",
            object=note,
            actor=actor_id,
        )

        payload = jsonable_encoder(activity, exclude_none=True)

        resp = self.client.post(f"/actors/{actor_id}/inbox", json=payload)
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)

    def test_post_actor_inbox_reject_unknown_object(self):
        # When posting an object that is not an Activity, we should expect a 422 Unprocessable Entity
        # even if it is a valid AS object.
        actor_id = self._get_first_actor_id()

        note = as_Note(
            id="urn:uuid:test-note",
            content="This is a test note.",
        )

        payload = jsonable_encoder(note, exclude_none=True)

        resp = self.client.post(f"/actors/{actor_id}/inbox", json=payload)
        self.assertEqual(
            resp.status_code, status.HTTP_422_UNPROCESSABLE_CONTENT
        )


if __name__ == "__main__":
    unittest.main()
