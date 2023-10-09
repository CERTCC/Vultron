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

import vultron.bt.embargo_management.conditions as emc
from vultron.bt.base.composites import FallbackNode
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.embargo_management.states import EM


class MockState:
    q_em = None
    pass


class TestEmbargoManagementConditions(unittest.TestCase):
    def setUp(self):
        self.emstates = (
            EM.NO_EMBARGO,
            EM.PROPOSED,
            EM.ACTIVE,
            EM.REVISE,
            EM.EXITED,
        )
        self.checks = {
            EM.NO_EMBARGO: emc.EMinStateNone,
            EM.PROPOSED: emc.EMinStateProposed,
            EM.ACTIVE: emc.EMinStateActive,
            EM.REVISE: emc.EMinStateRevise,
            EM.EXITED: emc.EMinStateExited,
        }

    def tearDown(self):
        pass

    def test_q_em_in_whatever(self):
        for expect_success, check in self.checks.items():
            c = check()
            c.bb = MockState()
            c.bb.q_em = expect_success
            self.assertEqual(
                NodeStatus.SUCCESS, c.tick()
            ), f"State {expect_success} should have succeeded"

            expect_fails = [x for x in self.emstates if x != expect_success]
            for state in expect_fails:
                c.bb.q_em = state
                self.assertEqual(
                    NodeStatus.FAILURE, c.tick()
                ), f"State {state} should have failed"

    def test_em_in_state(self):
        """Test that the EMinState node is instantiated correctly

        Returns:

        """
        node = emc.EMinState()
        self.assertEqual(
            node.state, None
        ), f"The state is not correct: {node.state} should be None"
        self.assertEqual(
            node.key, "q_em"
        ), f"The key is not correct: {node.key} should be q_em"

    def test_em_in_state_active(self):
        """Test that the EMinStateActive node is instantiated with the correct state

        Returns:

        """
        node = emc.EMinStateActive()

        self.assertEqual(node.state, EM.ACTIVE), "The state is not correct"
        self.assertIsInstance(
            node, emc.EMinState
        ), "The node is not an instance of EMinState"

    def test_em_in_state_none(self):
        """Test that the EMinStateNone node is instantiated with the correct state

        Returns:

        """
        node = emc.EMinStateNone()
        self.assertEqual(node.state, EM.NO_EMBARGO), "The state is not correct"
        self.assertIsInstance(
            node, emc.EMinState
        ), "The node is not an instance of EMinState"

    def test_em_in_state_proposed(self):
        """Test that the EMinStateProposed node is instantiated with the correct state

        Returns:

        """
        node = emc.EMinStateProposed()
        self.assertEqual(node.state, EM.PROPOSED), "The state is not correct"
        self.assertIsInstance(
            node, emc.EMinState
        ), "The node is not an instance of EMinState"

    def test_em_in_state_revise(self):
        """Test that the EMinStateRevise node is instantiated with the correct state

        Returns:

        """
        node = emc.EMinStateRevise()
        self.assertEqual(node.state, EM.REVISE), "The state is not correct"
        self.assertIsInstance(
            node, emc.EMinState
        ), "The node is not an instance of EMinState"

    def test_em_in_state_exited(self):
        """Test that the EMinStateExited node is instantiated with the correct state

        Returns:

        """
        node = emc.EMinStateExited()
        self.assertEqual(node.state, EM.EXITED), "The state is not correct"
        self.assertIsInstance(
            node, emc.EMinState
        ), "The node is not an instance of EMinState"

    def _test_for_states_in_fallback(self, expected_states, node):
        """Test that the FallbackNode is instantiated with the correct children

        Args:
            expected_states: the list of states that should be in the
                children
            node: the FallbackNode to test

        Returns:
            None
        """
        # make sure the node is a FallbackNode
        self.assertIsInstance(node, FallbackNode), "The node is not a FallbackNode"

        # make sure the number of children is correct
        self.assertEqual(
            len(node._children), len(expected_states)
        ), "The number of children is not correct"

        # children are instantiated from the list of classes in _children
        for child, _child in zip(node.children, node._children):
            self.assertIsInstance(
                child, _child
            ), f"The child {child} is not an instance of {_child}"
            # make sure the child inherits from EMinState
            self.assertIsInstance(
                child, emc.EMinState
            ), f"The child {child} does not inherit from EMinState"

        # make sure the states are in the children
        states = [child.state for child in node._children]
        for state in expected_states:
            self.assertIn(state, states), f"The state {state} is not in the children"

    def test_em_in_state_active_or_revise(self):
        """Test that the FallbackNode is instantiated with the correct children

        Returns:

        """
        node = emc.EMinStateActiveOrRevise()
        expected_states = [EM.ACTIVE, EM.REVISE]

        self._test_for_states_in_fallback(expected_states, node)

    def test_em_in_state_none_or_exited(self):
        """Test that the FallbackNode is instantiated with the correct children

        Returns:

        """
        node = emc.EMinStateNoneOrExited()
        expected_states = [EM.NO_EMBARGO, EM.EXITED]

        self._test_for_states_in_fallback(expected_states, node)

    def test_em_in_state_propose_or_revise(self):
        """Test that the FallbackNode is instantiated with the correct children

        Returns:

        """
        node = emc.EMinStateProposeOrRevise()
        expected_states = [EM.PROPOSED, EM.REVISE]

        self._test_for_states_in_fallback(expected_states, node)

    def test_em_in_state_none_or_proposed_or_revise(self):
        """Test that the FallbackNode is instantiated with the correct children

        Returns:

        """
        node = emc.EMinStateNoneOrProposeOrRevise()
        expected_states = [EM.NO_EMBARGO, EM.PROPOSED, EM.REVISE]

        self._test_for_states_in_fallback(expected_states, node)


if __name__ == "__main__":
    unittest.main()
