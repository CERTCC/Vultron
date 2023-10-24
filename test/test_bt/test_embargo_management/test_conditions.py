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
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.embargo_management.states import EM


class MockState:
    q_em = None
    pass


class TestEmbargoManagementConditions(unittest.TestCase):
    def setUp(self):
        self.emstates = tuple(EM)
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

    def test_em_in_state_active(self):
        """Test that the EMinStateActive node is instantiated with the correct state

        Returns:

        """
        cls = emc.EMinStateActive
        should_succeed = (EM.ACTIVE,)

        self._test_in_state(cls, should_succeed)

    def test_em_in_state_none(self):
        """Test that the EMinStateNone node is instantiated with the correct state

        Returns:

        """
        cls = emc.EMinStateNone
        should_succeed = (EM.NO_EMBARGO,)

        self._test_in_state(cls, should_succeed)

    def _test_in_state(self, cls, expected_states):
        for state in EM:
            node = cls()
            node.bb = MockState()
            node.bb.q_em = state

            node.tick()

            if state in expected_states:
                self.assertEqual(NodeStatus.SUCCESS, node.status)
            else:
                self.assertEqual(NodeStatus.FAILURE, node.status)

    def test_em_in_state_proposed(self):
        """Test that the EMinStateProposed node is instantiated with the correct state

        Returns:

        """
        cls = emc.EMinStateProposed
        should_succeed = (EM.PROPOSED,)

        self._test_in_state(cls, should_succeed)

    def test_em_in_state_revise(self):
        """Test that the EMinStateRevise node is instantiated with the correct state

        Returns:

        """
        cls = emc.EMinStateRevise
        should_succeed = (EM.REVISE,)

        self._test_in_state(cls, should_succeed)

    def test_em_in_state_exited(self):
        """Test that the EMinStateExited node is instantiated with the correct state

        Returns:

        """
        cls = emc.EMinStateExited
        should_succeed = (EM.EXITED,)

        self._test_in_state(cls, should_succeed)

    def test_em_in_state_active_or_revise(self):
        """Test that the FallbackNode is instantiated with the correct children

        Returns:

        """
        node = emc.EMinStateActiveOrRevise
        expected_states = (EM.ACTIVE, EM.REVISE)

        self._test_in_state(node, expected_states)

    def test_em_in_state_none_or_exited(self):
        """Test that the FallbackNode is instantiated with the correct children

        Returns:

        """
        node = emc.EMinStateNoneOrExited
        expected_states = (EM.NO_EMBARGO, EM.EXITED)

        self._test_in_state(node, expected_states)

    def test_em_in_state_propose_or_revise(self):
        """Test that the FallbackNode is instantiated with the correct children

        Returns:

        """
        node = emc.EMinStateProposeOrRevise
        expected_states = (EM.PROPOSED, EM.REVISE)

        self._test_in_state(node, expected_states)

    def test_em_in_state_none_or_proposed_or_revise(self):
        """Test that the FallbackNode is instantiated with the correct children

        Returns:

        """
        node = emc.EMinStateNoneOrProposeOrRevise
        expected_states = (EM.NO_EMBARGO, EM.PROPOSED, EM.REVISE)

        self._test_in_state(node, expected_states)


if __name__ == "__main__":
    unittest.main()
