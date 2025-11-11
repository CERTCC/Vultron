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

from vultron.api.v2.backend.handlers.accept import (
    accept_offer_handler,
    rm_validate_report,
)
from vultron.api.v2.data import get_datalayer
from vultron.api.v2.data.enums import OfferStatusEnum
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Offer,
    as_Accept,
)
from vultron.as_vocab.base.objects.actors import as_Person, as_Organization
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.bt.report_management.states import RM


class TestAcceptHandlers(unittest.TestCase):
    def setUp(self):
        self.finder = as_Person(name="Test Finder")
        self.vendor = as_Organization(name="Test Vendor")

        self.report = VulnerabilityReport(
            content="Test vulnerability report content",
            attributed_to=self.finder,
        )
        self.offer = as_Offer(
            to=self.vendor,
            actor=self.finder,
            object=self.report,
        )
        self.accept = as_Accept(
            to=self.finder.as_id,
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

    @patch("vultron.api.v2.backend.handlers.accept.rm_validate_report")
    def test_accept_offer_handler_routes_offer_reports(
        self, mock_rm_validate_report
    ):
        activity = self.accept

        accept_offer_handler(actor_id=self.vendor.as_id, activity=activity)

        mock_rm_validate_report.assert_called_once_with(activity)

    @unittest.skip("TODO: implement this test")
    def test_accept_offer_handler_routers_actor_recommendation(self):
        pass

    @unittest.skip("TODO: implement this test")
    def test_accept_offer_handler_routes_case_ownership_transfer(self):
        pass

    @unittest.skip("TODO: implement this test")
    def test_acccept_offer_warns_on_unhandled_offer_subtypes(self):
        pass

    @unittest.skip("TODO: implement this test")
    def test_accept_invite_handler(self):
        pass

    @unittest.skip("TODO: implement this test")
    def test_em_accept_embargo(self):
        pass

    @unittest.skip("TODO: implement this test")
    def rm_accept_invite_to_case(self):
        pass

    @patch("vultron.api.v2.backend.handlers.accept.set_status")
    @patch("vultron.api.v2.backend.handlers.accept.rm_validate_report")
    def test_rm_validate_report(
        self, mock_rm_validate_report, mock_set_status
    ):
        self.dl.create(self.accept)
        self.assertIn(self.accept.as_id, get_datalayer())

        activity = self.accept

        rm_validate_report(activity)

        mock_set_status.assert_called()

        matches = []
        for args in mock_set_status.call_args_list:
            # the first argument is the status object
            obj = args[0][0]

            match obj.object_type:
                # we should see both the Offer and the VulnerabilityReport being updated
                case "Offer":
                    self.assertEqual(OfferStatusEnum.ACCEPTED, obj.status)
                    matches.append("Offer")
                case "VulnerabilityReport":
                    self.assertEqual(RM.VALID, obj.status)
                    matches.append("VulnerabilityReport")

        self.assertIn("Offer", matches)
        self.assertIn("VulnerabilityReport", matches)

        pass


if __name__ == "__main__":
    unittest.main()
