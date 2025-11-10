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

import unittest
from copy import deepcopy

import vultron.bt.case_state.transitions as cst
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.states import ActorState
from vultron.case_states.states import (
    AttackObservation,
    CS,
    ExploitPublication,
    FixDeployment,
    FixReadiness,
    PublicAwareness,
    VendorAwareness,
)


class MyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.bb = ActorState()

    def _test_q_cs_to_something(self):
        """
        Helper function to test the q_cs_to_* functions

        Expects the following class attributes to be set:
        - cls2test: the class to test
        - expected_value: the expected value of the state after the transition
        - attrib2check: the variable to check for the expected value

        Returns:

        """
        node = self.cls2test()
        node.bb = self.bb

        for state in CS:
            with self.subTest(state=state):
                original_state = deepcopy(state)

                expect_new_state = state.name.replace(
                    node.target_state.lower(), node.target_state
                )
                valid_new_state = expect_new_state in CS.__members__

                self.bb.q_cs = state

                self.assertEqual(state, node.bb.q_cs)

                node.tick()

                # should always succeed
                self.assertEqual(NodeStatus.SUCCESS, node.status)

                if node.target_state in state.name:
                    # shouldn't change if we're already there
                    self.assertEqual(original_state, node.bb.q_cs)
                    return

                # if you got here, we're not already in the new state
                if not valid_new_state:
                    # shouldn't change if new state is invalid
                    self.assertEqual(original_state, node.bb.q_cs)
                    return

                # if you got here, the new state is valid

                # should change if we're not already there
                self.assertNotEqual(original_state, node.bb.q_cs)

                # only diff should be the V
                self.assertEqual(
                    node.bb.q_cs.name,
                    original_state.name.replace(
                        node.target_state.lower(), node.target_state
                    ),
                )

                # dive in to find the actual state value we want to check
                val2check = self.bb.q_cs.value
                for attr in self.attrib2check.split("."):
                    val2check = getattr(val2check, attr)

                # make sure the actual state value is correct
                self.assertEqual(self.expected_value, val2check)

    def test_q_cs_to_V(self):
        self.cls2test = cst.q_cs_to_V
        self.expected_value = VendorAwareness.VENDOR_AWARE
        self.attrib2check = "vfd_state.value.vendor_awareness"

        self._test_q_cs_to_something()

    def test__q_cs_to_F(self):
        self.cls2test = cst._q_cs_to_F
        self.expected_value = FixReadiness.FIX_READY
        self.attrib2check = "vfd_state.value.fix_readiness"

        self._test_q_cs_to_something()

    def _test_q_cs_to_something_with_precondition(self):
        node = self.cls2test()
        node.bb = self.bb

        for state in CS:
            self.bb.q_cs = state
            node.tick()

            if self.expect_fail_when in state.name:
                # should not work
                self.assertEqual(NodeStatus.FAILURE, node.status)
            else:
                self.assertEqual(NodeStatus.SUCCESS, node.status)

        attrib2check = self.bb.q_cs.value
        for attr in self.attrib2check.split("."):
            attrib2check = getattr(attrib2check, attr)

        self.assertEqual(self.expected_value, attrib2check)

    def test_q_cs_to_F(self):
        self.cls2test = cst.q_cs_to_F
        self.expected_value = FixReadiness.FIX_READY
        self.attrib2check = "vfd_state.value.fix_readiness"
        self.expect_fail_when = "v"

        self._test_q_cs_to_something_with_precondition()

    def test__q_cs_to_D(self):
        self.cls2test = cst._q_cs_to_D
        self.expected_value = FixDeployment.FIX_DEPLOYED
        self.attrib2check = "vfd_state.value.fix_deployment"

        self._test_q_cs_to_something()

    def test_q_cs_to_D(self):
        self.cls2test = cst.q_cs_to_D
        self.expected_value = FixDeployment.FIX_DEPLOYED
        self.attrib2check = "vfd_state.value.fix_deployment"
        self.expect_fail_when = "f"

        self._test_q_cs_to_something_with_precondition()

    def test_q_cs_to_P(self):
        self.cls2test = cst.q_cs_to_P
        self.expected_value = PublicAwareness.PUBLIC_AWARE
        self.attrib2check = "pxa_state.value.public_awareness"

        self._test_q_cs_to_something()

    def test_q_cs_to_X(self):
        self.cls2test = cst.q_cs_to_X
        self.expected_value = ExploitPublication.EXPLOIT_PUBLIC
        self.attrib2check = "pxa_state.value.exploit_publication"

        self._test_q_cs_to_something()

    def test_q_cs_to_A(self):
        self.cls2test = cst.q_cs_to_A
        self.expected_value = AttackObservation.ATTACKS_OBSERVED
        self.attrib2check = "pxa_state.value.attack_observation"


if __name__ == "__main__":
    unittest.main()
