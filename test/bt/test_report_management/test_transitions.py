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

import vultron.bt.report_management.transitions as rmt
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.report_management.states import RM


class MockActorState:
    def __init__(self):
        self.q_rm = None
        self.q_rm_history = []


class MyTestCase(unittest.TestCase):
    def _test_generic_transition(self, cls, allowed, target):
        for rm_state in RM:
            node = cls()

            node.bb = MockActorState()

            node.bb.q_rm = rm_state
            self.assertEqual(rm_state, node.bb.q_rm)

            node.tick()

            if rm_state in allowed:
                # if the transition is allowed, the node should succeed
                self.assertEqual(NodeStatus.SUCCESS, node.status)
                # and the state should change to the target
                self.assertEqual(node.bb.q_rm, target)
            else:
                # if the transition is not allowed, the node should fail
                self.assertEqual(NodeStatus.FAILURE, node.status)
                # and the state should not change
                self.assertEqual(node.bb.q_rm, rm_state)

    def test_q_rm_to_R(self):
        self._test_generic_transition(
            rmt.q_rm_to_R, [RM.START, RM.RECEIVED], target=RM.RECEIVED
        )

    def test_q_rm_to_I(self):
        self._test_generic_transition(
            rmt.q_rm_to_I, [RM.RECEIVED, RM.INVALID], target=RM.INVALID
        )

    def test_q_rm_to_V(self):
        self._test_generic_transition(
            rmt.q_rm_to_V, [RM.RECEIVED, RM.INVALID, RM.VALID], target=RM.VALID
        )

    def test_q_rm_to_D(self):
        self._test_generic_transition(
            rmt.q_rm_to_D,
            [RM.VALID, RM.ACCEPTED, RM.DEFERRED],
            target=RM.DEFERRED,
        )

    def test_q_rm_to_A(self):
        self._test_generic_transition(
            rmt.q_rm_to_A,
            [RM.VALID, RM.DEFERRED, RM.ACCEPTED],
            target=RM.ACCEPTED,
        )

    def test_q_rm_to_C(self):
        self._test_generic_transition(
            rmt.q_rm_to_C,
            [RM.INVALID, RM.DEFERRED, RM.ACCEPTED, RM.CLOSED],
            target=RM.CLOSED,
        )


if __name__ == "__main__":
    unittest.main()
