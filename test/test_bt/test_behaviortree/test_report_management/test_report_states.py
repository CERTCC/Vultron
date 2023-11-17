#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
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
#
#  See LICENSE for details

import unittest

from vultron.bt.report_management.states import (
    RM,
    RM_ACTIVE,
    RM_CLOSABLE,
    RM_UNCLOSED,
)


class MyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_report_management_states(self):
        self.assertIs(RM.START, RM.S)
        self.assertIs(RM.RECEIVED, RM.R)
        self.assertIs(RM.INVALID, RM.I)
        self.assertIs(RM.VALID, RM.V)
        self.assertIs(RM.DEFERRED, RM.D)
        self.assertIs(RM.ACCEPTED, RM.A)
        self.assertIs(RM.CLOSED, RM.C)

    def test_report_management_state_names(self):
        self.assertEqual("REPORT_MANAGEMENT_START", RM.S.name)
        self.assertEqual("REPORT_MANAGEMENT_RECEIVED", RM.R.name)
        self.assertEqual("REPORT_MANAGEMENT_INVALID", RM.I.name)
        self.assertEqual("REPORT_MANAGEMENT_VALID", RM.V.name)
        self.assertEqual("REPORT_MANAGEMENT_DEFERRED", RM.D.name)
        self.assertEqual("REPORT_MANAGEMENT_ACCEPTED", RM.A.name)
        self.assertEqual("REPORT_MANAGEMENT_CLOSED", RM.C.name)

    def test_rm_closable(self):
        self.assertNotIn(RM.S, RM_CLOSABLE)
        self.assertNotIn(RM.R, RM_CLOSABLE)

        self.assertIn(RM.I, RM_CLOSABLE)

        self.assertNotIn(RM.V, RM_CLOSABLE)

        self.assertIn(RM.D, RM_CLOSABLE)
        self.assertIn(RM.A, RM_CLOSABLE)

        self.assertNotIn(RM.C, RM_CLOSABLE)

    def test_rm_unclosed(self):
        self.assertIn(RM.S, RM_UNCLOSED)
        self.assertIn(RM.R, RM_UNCLOSED)
        self.assertIn(RM.I, RM_UNCLOSED)
        self.assertIn(RM.V, RM_UNCLOSED)
        self.assertIn(RM.D, RM_UNCLOSED)
        self.assertIn(RM.A, RM_UNCLOSED)

        self.assertNotIn(RM.C, RM_UNCLOSED)

    def test_rm_active(self):
        self.assertNotIn(RM.S, RM_ACTIVE)

        self.assertIn(RM.R, RM_ACTIVE)

        self.assertNotIn(RM.I, RM_ACTIVE)

        self.assertIn(RM.V, RM_ACTIVE)

        self.assertNotIn(RM.D, RM_ACTIVE)

        self.assertIn(RM.A, RM_ACTIVE)

        self.assertNotIn(RM.C, RM_ACTIVE)


if __name__ == "__main__":
    unittest.main()
