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

import vultron.bt.report_management.conditions as rmc
from vultron.bt.base.node_status import NodeStatus


class MockState:
    q_rm = None
    pass


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.rmstates = (
            rmc.RM.R,
            rmc.RM.I,
            rmc.RM.V,
            rmc.RM.A,
            rmc.RM.C,
            rmc.RM.D,
            rmc.RM.S,
        )
        self.checks = {
            rmc.RM.S: rmc.RMinStateStart,
            rmc.RM.R: rmc.RMinStateReceived,
            rmc.RM.I: rmc.RMinStateInvalid,
            rmc.RM.V: rmc.RMinStateValid,
            rmc.RM.D: rmc.RMinStateDeferred,
            rmc.RM.A: rmc.RMinStateAccepted,
            rmc.RM.C: rmc.RMinStateClosed,
        }
        self.not_checks = {
            rmc.RM.S: rmc.RMnotInStateStart,
            rmc.RM.C: rmc.RMnotInStateClosed,
        }

    def tearDown(self):
        pass

    def test_q_rm_in_whatever(self):
        for expect_success, check in self.checks.items():
            c = check()
            c.bb = MockState()
            c.bb.q_rm = expect_success
            self.assertEqual(NodeStatus.SUCCESS, c.tick())

            for state in [x for x in self.rmstates if x != expect_success]:
                c.bb.q_rm = state
                self.assertEqual(NodeStatus.FAILURE, c.tick())

    def test_q_rm_not_in_whatever(self):
        for expect_fail, check in self.not_checks.items():
            c = check()
            c.bb = MockState()
            c.setup()
            c.bb.q_rm = expect_fail
            self.assertEqual(NodeStatus.FAILURE, c.tick())

            for state in [x for x in self.rmstates if x != expect_fail]:
                c.bb.q_rm = state
                self.assertEqual(NodeStatus.SUCCESS, c.tick())

    def test_RMinState(self):
        c = rmc.RMinState()
        c.bb = MockState()
        c.setup()
        self.assertEqual(c.key, "q_rm")


if __name__ == "__main__":
    unittest.main()
