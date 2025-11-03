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

import unittest

from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from vultron.api.data import _THINGS, wrap_offer
from vultron.api.v2.routers import backend
from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport


class MyTestCase(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(backend.router)
        self.client = TestClient(app)
        self.report = VulnerabilityReport()
        self.offer = as_Offer(
            actor="urn:uuid:test-actor", as_object=self.report
        )

    def tearDown(self):
        _THINGS.clear()

    def test_get_offers(self):
        response = self.client.get("/datalayer/offers")
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsInstance(response.json(), list)
        self.assertEqual(
            0, len(response.json())
        )  # Assuming no offers initially

        wrapped = wrap_offer(self.offer)
        _THINGS.received.offers[wrapped.object_id] = wrapped

        response = self.client.get("/datalayer/offers")
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()))

        offer_id = self.offer.as_id

        self.assertIn(offer_id, response.json()[0]["id"])

    def test_get_offer_by_id(self):
        wrapped = wrap_offer(self.offer)
        _THINGS.received.offers[wrapped.object_id] = wrapped

        response = self.client.get(
            f"/datalayer/offers/", params={"offer_id": self.offer.as_id}
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(self.offer.as_id, response.json()["id"])
        self.assertEqual(self.offer.actor, response.json()["actor"])

    def test_post_offer(self):

        offer = jsonable_encoder(self.offer, exclude_none=True)

        response = self.client.post(
            "/datalayer/offers",
            json=offer,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertIn("Location", response.headers)
        self.assertIn(self.offer.as_id, response.headers["Location"])

    def test_get_reports(self):
        response = self.client.get("/datalayer/reports")
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsInstance(response.json(), list)
        self.assertEqual(
            0, len(response.json())
        )  # Assuming no reports initially

        _THINGS.received.reports[self.report.as_id] = self.report

        response = self.client.get("/datalayer/reports")
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()))

        report_id = self.report.as_id

        self.assertIn(report_id, response.json()[0]["id"])

    def test_post_report(self):
        report = jsonable_encoder(self.report, exclude_none=True)

        response = self.client.post(
            "/datalayer/reports",
            json=report,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertIn("Location", response.headers)
        self.assertIn(self.report.as_id, response.headers["Location"])

        received = _THINGS.received.reports.pop(self.report.as_id, None)
        self.assertIsNotNone(received)
        self.assertEqual(self.report.as_id, received.as_id)

    def test_get_report_by_id(self):
        _THINGS.received.reports[self.report.as_id] = self.report

        response = self.client.get(
            f"/datalayer/reports/", params={"id": self.report.as_id}
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(self.report.as_id, response.json()["id"])


if __name__ == "__main__":
    unittest.main()
