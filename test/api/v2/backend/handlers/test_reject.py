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
from unittest.mock import patch

from vultron.api.v2.backend.handlers.reject import (
    reject_offer,
    rm_close_report,
)
from vultron.api.v2.data import get_datalayer
from vultron.api.v2.data.enums import OfferStatusEnum
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Offer,
    as_Reject,
)
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.bt.report_management.states import RM


class RejectHandlerTestCase(unittest.TestCase):
    def setUp(self):
        self.finder = as_Actor(
            name="Test Finder",
        )
        self.vendor = as_Actor(
            name="Test Vendor",
        )
        self.report = VulnerabilityReport(
            attributed_to=self.finder.as_id,
            content="This is a test vulnerability report.",
        )
        self.offer = as_Offer(
            actor=self.finder.as_id,
            object=self.report,
        )
        self.reject = as_Reject(
            actor=self.vendor.as_id,
            object=self.offer,
        )

        self.dl = get_datalayer()

        self.dl.create(self.finder)
        self.dl.create(self.vendor)
        self.dl.create(self.report)
        self.dl.create(self.offer)

    def tearDown(self):
        self.dl.clear()

    def test_setup(self):
        self.assertEqual(self.reject.as_type, "Reject")
        self.assertEqual(self.reject.as_object.as_type, "Offer")
        self.assertEqual(
            self.reject.as_object.as_object.as_type, "VulnerabilityReport"
        )

    @patch("vultron.api.v2.data.store.DataStore.create")
    @patch("vultron.api.v2.backend.handlers.reject.rm_close_report")
    def test_reject_offer(self, mock_rm_close_report, mock_datalayer_create):
        activity = self.reject

        self.assertNotIn(activity.as_id, self.dl)

        reject_offer(actor_id=self.vendor.as_id, activity=activity)
        mock_datalayer_create.assert_called_once_with(activity)

        # because we mock datalayer.create, the activity won't actually be stored
        self.assertNotIn(activity.as_id, self.dl)

        mock_rm_close_report.assert_called_once_with(activity)

    @patch("vultron.api.v2.backend.handlers.reject.set_status")
    def test_rm_close_report(self, mock_set_status):
        self.dl.create(self.reject)
        activity = self.reject

        rm_close_report(activity)

        mock_set_status.assert_called()

        matches = []
        for args in mock_set_status.call_args_list:
            # the first argument is the status object
            obj = args[0][0]

            match obj.object_type:
                # we should see both the Offer and the VulnerabilityReport being updated
                case "Offer":
                    self.assertEqual(obj.status, OfferStatusEnum.REJECTED)
                    matches.append("Offer")
                case "VulnerabilityReport":
                    self.assertEqual(obj.status, RM.CLOSED)
                    matches.append("VulnerabilityReport")

        self.assertIn("Offer", matches)
        self.assertIn("VulnerabilityReport", matches)

    def test_tentative_reject_offer(self):
        self.assertEqual(True, False)  # add assertion here

    def test_rm_invalidate_report(self):
        self.assertEqual(True, False)  # add assertion here

    def test_something(self):
        self.assertEqual(True, False)  # add assertion here


if __name__ == "__main__":
    unittest.main()
