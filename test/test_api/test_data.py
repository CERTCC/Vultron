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

from vultron.api import data
from vultron.api.data import InMemoryDataLayer, wrap_offer
from vultron.as_vocab.base.objects.activities.transitive import as_Offer


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.things = data._THINGS
        self.dl = InMemoryDataLayer()

    def tearDown(self):
        self.things.clear()

    def test_collection_initialization(self):
        c = data.Collection()
        for attr in ["offers", "invites", "reports", "cases"]:
            self.assertTrue(hasattr(c, attr))
            self.assertIsInstance(getattr(c, attr), list)
            self.assertEqual(0, len(getattr(c, attr)))

    def test_memorystore_initialization(self):
        ms = data.MemoryStore()
        self.assertTrue(hasattr(ms, "received"))
        self.assertIsInstance(ms.received, data.Collection)

    def test_in_memory_datalayer_initialization(self):
        dl = data.InMemoryDataLayer()
        self.assertIsInstance(dl, data.DataLayer)
        for attribute in data.DataLayer.__dict__.keys():
            if attribute.startswith("_"):
                # Skip special and private attributes
                continue

            self.assertTrue(hasattr(dl, attribute))

    def test_clear_things(self):
        self.things.received.reports.append("test_report")
        self.assertEqual(len(self.things.received.reports), 1)
        self.things.clear()
        self.assertEqual(len(self.things.received.reports), 0)

    def test_data_layer_receive_report(self):
        report = "test_report"

        self.assertEqual(0, len(self.things.received.reports))
        self.dl.receive_report(report)
        self.assertIn(report, self.things.received.reports)

    def test_data_layer_get_all_reports(self):
        report1 = "test_report_1"
        report2 = "test_report_2"

        self.things.received.reports.extend([report1, report2])
        reports = self.dl.get_all_reports()
        self.assertIn(report1, reports)
        self.assertIn(report2, reports)

    def test_data_layer_receive_offer(self):
        offer = as_Offer(actor="urn:uuid:test-actor", as_object="test_object")

        self.assertEqual(0, len(self.things.received.offers))
        self.dl.receive_offer(offer)

        offers = [wrapped.object for wrapped in self.things.received.offers]

        self.assertIn(offer, offers)

    def test_data_layer_get_all_offers(self):
        offer1 = as_Offer(
            actor="urn:uuid:test-actor-1", as_object="test_object_1"
        )
        offer2 = as_Offer(
            actor="urn:uuid:test-actor-2", as_object="test_object_2"
        )

        wrapped1 = wrap_offer(offer1)
        wrapped2 = wrap_offer(offer2)

        self.things.received.offers.extend([wrapped1, wrapped2])
        offers = self.dl.get_all_offers()
        self.assertIn(offer1, offers)
        self.assertIn(offer2, offers)

    def test_wrap_offer(self):
        offer = as_Offer(actor="urn:uuid:test-actor", as_object="test_object")
        wrapped = wrap_offer(offer)

        self.assertEqual(wrapped.object_id, offer.as_id)
        self.assertEqual(wrapped.object, offer)
        self.assertEqual(wrapped.object_status, data.OfferStatus.RECEIVED)

    def test_data_layer_receive_case(self):
        case = "test_case"

        self.assertEqual(0, len(self.things.received.cases))
        self.dl.receive_case(case)
        self.assertIn(case, self.things.received.cases)

    def test_data_layer_get_all_cases(self):
        case1 = "test_case_1"
        case2 = "test_case_2"

        self.things.received.cases.extend([case1, case2])
        cases = self.dl.get_all_cases()
        self.assertIn(case1, cases)
        self.assertIn(case2, cases)

    def test_get_datalayer(self):
        dl = data.get_datalayer()
        self.assertIsInstance(dl, data.DataLayer)


if __name__ == "__main__":
    unittest.main()
