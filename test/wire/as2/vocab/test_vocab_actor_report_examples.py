#  Copyright (c) 2024-2025 Carnegie Mellon University and Contributors.
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
import unittest
from typing import cast

import vultron.wire.as2.vocab.examples.vocab_examples as examples
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Create,
    as_Offer,
    as_Read,
    as_Reject,
    as_TentativeReject,
)
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Actor,
    as_Organization,
)
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)


class TestVocabActorExamples(unittest.TestCase):
    def test_finder(self):
        finder = examples.finder()
        self.assertIsInstance(finder, as_Actor)

    def test_vendor(self):
        vendor = examples.vendor()
        self.assertIsInstance(vendor, as_Actor)

    def test_coordinator(self):
        coordinator = examples.coordinator()
        self.assertIsInstance(coordinator, as_Actor)

        self.assertTrue(hasattr(coordinator, "to_json"))
        self.assertIsInstance(coordinator, as_Organization)
        assert coordinator.name is not None
        self.assertIn("coordinator", coordinator.name.lower())


class TestVocabReportExamples(unittest.TestCase):
    def test_report(self):
        report = examples.gen_report()
        self.assertIsInstance(report, as_Object)
        self.assertIsInstance(report, VulnerabilityReport)

        self.assertTrue(hasattr(report, "to_json"))
        json = report.to_json()
        self.assertIsInstance(json, str)

    def test_create_report(self):
        create_report = examples.create_report()
        self.assertIsInstance(create_report, as_Activity)
        finder = examples.finder()
        report = examples.gen_report()

        self.assertIsInstance(create_report, as_Create)
        self.assertEqual(create_report.type_, "Create")
        self.assertEqual(create_report.actor, finder.id_)
        self.assertEqual(create_report.object_, report)

    def test_submit_report(self):
        submit_report = examples.submit_report()
        self.assertIsInstance(submit_report, as_Activity)
        finder = examples.finder()
        report = examples.gen_report()

        self.assertIsInstance(submit_report, as_Offer)
        self.assertEqual(submit_report.type_, "Offer")
        self.assertEqual(submit_report.actor, finder.id_)
        self.assertEqual(submit_report.object_, report)

    def test_read_report(self):
        read_report = examples.read_report()
        self.assertIsInstance(read_report, as_Activity)
        vendor = examples.vendor()
        report = examples.gen_report()

        self.assertIsInstance(read_report, as_Read)
        self.assertEqual(read_report.type_, "Read")
        self.assertEqual(read_report.actor, vendor.id_)
        self.assertEqual(read_report.object_, report)

    def test_validate_report(self):
        activity = examples.validate_report(verbose=True)
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        finder = examples.finder()
        report = examples.gen_report()

        self.assertIsInstance(activity, as_Accept)
        self.assertEqual(activity.type_, "Accept")
        self.assertEqual(activity.actor, vendor)

        offer = cast(as_Offer, activity.object_)
        self.assertEqual(offer.type_, "Offer")
        self.assertEqual(offer.actor, finder)

        report_ = cast(VulnerabilityReport, offer.object_)
        self.assertEqual(report, report_)

    def test_invalidate_report(self):
        activity = examples.invalidate_report(verbose=True)
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        finder = examples.finder()
        report = examples.gen_report()

        self.assertIsInstance(activity, as_TentativeReject)
        self.assertEqual(activity.type_, "TentativeReject")
        self.assertEqual(activity.actor, vendor)

        offer = cast(as_Offer, activity.object_)
        self.assertEqual(offer.type_, "Offer")
        self.assertEqual(offer.actor, finder)

        report_ = cast(VulnerabilityReport, offer.object_)
        self.assertEqual(report, report_)

    def test_close_report(self):
        activity = examples.close_report(verbose=True)
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        finder = examples.finder()
        report = examples.gen_report()

        self.assertIsInstance(activity, as_Reject)
        self.assertEqual(activity.type_, "Reject")
        self.assertEqual(vendor, activity.actor)

        offer = cast(as_Offer, activity.object_)
        self.assertEqual(offer.type_, "Offer")
        self.assertEqual(offer.actor, finder)

        report_ = cast(VulnerabilityReport, offer.object_)
        self.assertEqual(report, report_)


if __name__ == "__main__":
    unittest.main()
