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

import vultron.bt.report_management.transitions as rmt
from vultron.bt.base.node_status import NodeStatus


class MockState:
    q_rm = None
    q_rm_history = []


class TestRMTransitions(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _test_rm_transition_factory(self, expect_success, end_state, factory):
        # Make sure the end state is in the list of expected success states
        if end_state not in expect_success:
            expect_success.append(end_state)

        # Expect failure for all other states
        expect_fail = [state for state in rmt.RM if state not in expect_success]

        for state in expect_success:
            # set up the node
            node = factory()
            node.bb = MockState()
            self.assertIsNotNone(node.bb)
            self.assertIsNone(node.bb.q_rm)
            node.bb.q_rm = state
            node.setup()
            self.assertIsNotNone(node.bb.q_rm)

            self.assertEqual(NodeStatus.SUCCESS, node.tick())

        for state in expect_fail:
            # set up the node
            node = factory()
            node.bb = MockState()
            self.assertIsNotNone(node.bb)
            self.assertIsNone(node.bb.q_rm)
            node.bb.q_rm = state
            node.setup()
            self.assertIsNotNone(node.bb.q_rm)

            self.assertEqual(NodeStatus.FAILURE, node.tick())

    def test_q_rm_to_R(self):
        expect_success = rmt._to_R.start_states
        end_state = rmt._to_R.end_state
        factory = rmt.q_rm_to_R
        self._test_rm_transition_factory(expect_success, end_state, factory)

    def test_q_rm_to_I(self):
        expect_success = rmt._to_I.start_states
        end_state = rmt._to_I.end_state
        factory = rmt.q_rm_to_I
        self._test_rm_transition_factory(expect_success, end_state, factory)

    def test_q_rm_to_V(self):
        expect_success = rmt._to_V.start_states
        end_state = rmt._to_V.end_state
        factory = rmt.q_rm_to_V
        self._test_rm_transition_factory(expect_success, end_state, factory)

    def test_q_rm_to_D(self):
        expect_success = rmt._to_D.start_states
        end_state = rmt._to_D.end_state
        factory = rmt.q_rm_to_D
        self._test_rm_transition_factory(expect_success, end_state, factory)

    def test_q_rm_to_A(self):
        expect_success = rmt._to_A.start_states
        end_state = rmt._to_A.end_state
        factory = rmt.q_rm_to_A
        self._test_rm_transition_factory(expect_success, end_state, factory)

    def test_q_rm_to_C(self):
        expect_success = rmt._to_C.start_states
        end_state = rmt._to_C.end_state
        factory = rmt.q_rm_to_C
        self._test_rm_transition_factory(expect_success, end_state, factory)


if __name__ == "__main__":
    unittest.main()
