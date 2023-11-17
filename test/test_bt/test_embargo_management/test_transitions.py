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

import vultron.bt.embargo_management.transitions as emt
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.embargo_management.states import EM


class MockState:
    q_em = None
    q_em_history = []


class TestEMTransitions(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _test_em_transition_factory(self, expect_success, end_state, factory):
        # Make sure the end state is in the list of expected success states
        if end_state not in expect_success:
            expect_success.append(end_state)

        # Expect failure for all other states
        expect_fail = [state for state in EM if state not in expect_success]

        for state in expect_success:
            # set up the node
            node = factory()
            node.bb = MockState()
            self.assertIsNotNone(node.bb)
            self.assertIsNone(node.bb.q_em)
            node.bb.q_em = state
            node.setup()
            self.assertIsNotNone(node.bb.q_em)

            self.assertEqual(NodeStatus.SUCCESS, node.tick()), state

        for state in expect_fail:
            # set up the node
            node = factory()
            node.bb = MockState()
            self.assertIsNotNone(node.bb)
            self.assertIsNone(node.bb.q_em)
            node.bb.q_em = state
            node.setup()
            self.assertIsNotNone(node.bb.q_em)
            self.assertEqual(NodeStatus.FAILURE, node.tick()), state

    def test_q_em_to_P(self):
        expect_success = emt._to_P.start_states
        end_state = emt._to_P.end_state
        factory = emt.q_em_to_P
        self._test_em_transition_factory(expect_success, end_state, factory)

    def test_q_em_to_A(self):
        expect_success = emt._to_A.start_states
        end_state = emt._to_A.end_state
        factory = emt.q_em_to_A
        self._test_em_transition_factory(expect_success, end_state, factory)

    def test_q_em_to_R(self):
        expect_success = emt._to_R.start_states
        end_state = emt._to_R.end_state
        factory = emt.q_em_to_R
        self._test_em_transition_factory(expect_success, end_state, factory)

    def test_q_em_R_to_A(self):
        expect_success = emt._R_to_A.start_states
        end_state = emt._R_to_A.end_state
        factory = emt.q_em_R_to_A
        self._test_em_transition_factory(expect_success, end_state, factory)

    def test_q_em_to_X(self):
        expect_success = emt._to_X.start_states
        end_state = emt._to_X.end_state
        factory = emt.q_em_to_X
        self._test_em_transition_factory(expect_success, end_state, factory)


if __name__ == "__main__":
    unittest.main()
