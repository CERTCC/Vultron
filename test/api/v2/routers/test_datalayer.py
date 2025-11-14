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
from fastapi.testclient import TestClient

from vultron.api.v2.data import get_datalayer
from vultron.api.v2.routers import datalayer
from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport


class MyTestCase(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(datalayer.router)
        self.client = TestClient(app)
        self.report = VulnerabilityReport()
        self.offer = as_Offer(
            actor="urn:uuid:test-actor", as_object=self.report
        )

        self.dl = get_datalayer()

    def tearDown(self):
        self.dl.clear()

    def test_empty_get_offers(self):
        response = self.client.get("/datalayer/Offers/")
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsInstance(response.json(), dict)
        self.assertEqual(0, len(response.json()))

    def test_get_offers(self):
        self.dl.create(self.offer)

        response = self.client.get("/datalayer/Offers/")
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()))

        offer_id = self.offer.as_id

        self.assertIn(offer_id, response.json())

    def test_get_offer_by_id(self):
        self.dl.create(self.offer)

        response = self.client.get(
            f"/datalayer/Offer/", params={"object_id": self.offer.as_id}
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(self.offer.as_id, response.json()["id"])
        self.assertEqual(self.offer.actor, response.json()["actor"])

    def test_get_empty_reports(self):
        response = self.client.get("/datalayer/VulnerabilityReports/")
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsInstance(response.json(), dict)
        self.assertEqual(0, len(response.json()))

    def test_get_reports(self):
        self.dl.create(self.report)

        response = self.client.get("/datalayer/VulnerabilityReports/")
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()))

        report_id = self.report.as_id

        self.assertIn(report_id, response.json())

    def test_get_reports_shortcut(self):
        self.dl.create(self.report)
        response = self.client.get("/datalayer/Reports/")
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()))

        report_id = self.report.as_id

        self.assertIn(report_id, response.json())

    def test_get_report_by_id(self):
        self.dl.create(self.report)

        response = self.client.get(
            f"/datalayer/Report/", params={"id": self.report.as_id}
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(self.report.as_id, response.json()["id"])

    def test_reset(self):
        self.dl.create(self.offer)
        self.dl.create(self.report)

        # confirm that they exist
        self.assertIsNotNone(self.dl.by_type("Offer"))
        self.assertIsNotNone(self.dl.by_type("VulnerabilityReport"))

        response = self.client.delete("/datalayer/reset")
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = self.client.get("/datalayer/Offers/")
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(0, len(response.json()))

        response = self.client.get("/datalayer/Reports/")
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(0, len(response.json()))


if __name__ == "__main__":
    unittest.main()
