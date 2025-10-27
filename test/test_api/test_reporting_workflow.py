#!/usr/bin/env python
"""
Test the reporting workflow
"""

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

from vultron.api.data import THINGS
from vultron.api.v2.backend.handlers.accept import rm_validate_report
from vultron.api.v2.backend.handlers.create import (
    rm_create_report,
    create_case,
)
from vultron.api.v2.backend.handlers.offer import rm_submit_report
from vultron.api.v2.backend.handlers.read import rm_read_report
from vultron.api.v2.backend.handlers.reject import (
    rm_close_report,
    rm_invalidate_report,
)
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Create,
    as_Offer,
    as_Read,
    as_Accept,
    as_TentativeReject,
    as_Reject,
)
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport


class TestReportingWorkflow(unittest.TestCase):
    def setUp(self):
        self.reporter = as_Actor(
            id="urn:uuid:reporter-1234",
            name="Test Reporter",
        )
        self.report = VulnerabilityReport(
            id="urn:uuid:report-5678",
            name="Test Vulnerability Report",
            summary="This is a test vulnerability report.",
            attributed_to=self.reporter,
        )
        self.coordinator = as_Actor(
            id="urn:uuid:coordinator-91011",
            name="Test Coordinator",
        )
        self.case = VulnerabilityCase(
            id="urn:uuid:case-121314",
            name="Test Vulnerability Case",
            vulnerability_reports=[self.report],
        )
        self.things = THINGS
        self.things.clear()

    def tearDown(self):
        self.things.clear()

    def test_StoredThings_initialization(self):
        for attr in ["sent", "received"]:
            self.assertTrue(hasattr(THINGS, attr))
            obj = getattr(self.things, attr)

            for subattr in ["offers", "invites", "reports", "cases"]:
                self.assertTrue(hasattr(obj, subattr))
                items = getattr(obj, subattr)
                self.assertIsInstance(items, list)
                self.assertFalse(items)

    def _test_activity(self, activity, handler):
        # capture logging output if needed
        try:
            result = handler(actor_id=self.reporter.as_id, activity=activity)
        except Exception as e:
            self.fail(f"Handler raised an exception: {e}")

        self.assertIsNone(result)  # The handler returns None

    def test_create_report(self):
        activity = as_Create(
            id="urn:uuid:create-91011",
            actor=self.reporter,
            object=self.report,
        )
        self._test_activity(activity, rm_create_report)

    def test_offer_report(self):
        activity = as_Offer(
            id="urn:uuid:offer-121314",
            actor=self.reporter,
            object=self.report,
        )
        self._test_activity(activity, rm_submit_report)

        # check side effects
        self.assertIn(activity, self.things.received.offers)
        self.assertIn(self.report, self.things.received.reports)

    def test_read_report(self):
        activity = as_Read(
            id="urn:uuid:read-151617",
            actor=self.reporter,
            object=self.report,
        )
        self._test_activity(activity, rm_read_report)  # No read handler yet

    def test_validate_report(self):
        activity = as_Accept(
            id="urn:uuid:accept-181920",
            actor=self.reporter,
            object=self.report,
        )
        self._test_activity(activity, rm_validate_report)

    def test_invalidate_report(self):
        activity = as_TentativeReject(
            id="urn:uuid:accept-212223",
            actor=self.reporter,
            object=self.report,
        )
        self._test_activity(activity, rm_invalidate_report)

    def test_create_case(self):
        activity = as_Create(
            id="urn:uuid:create-case-242526",
            actor=self.coordinator,
            object=self.case,
        )
        self._test_activity(activity, create_case)

    def test_close_report(self):
        activity = as_Reject(
            id="urn:uuid:reject-272829",
            actor=self.coordinator,
            object=self.report,
        )
        self._test_activity(activity, rm_close_report)


if __name__ == "__main__":
    unittest.main()
