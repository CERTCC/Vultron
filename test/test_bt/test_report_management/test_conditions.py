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

import vultron.bt.report_management.conditions as rmc
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.report_management.states import RM
from vultron.bt.states import ActorState


class MyTestCase(unittest.TestCase):
    def _test_generic_rm_in_state(self, cls, state):
        node = cls()
        node.bb = ActorState()

        self.assertEqual("q_rm", node.key)
        self.assertEqual(state, node.state)

        for rm_state in RM:
            node.bb.q_rm = rm_state

            node.tick()


            if rm_state == state:
                # success when they agree
                self.assertEqual(NodeStatus.SUCCESS, node.status)
            else:
                # failure when they disagree
                self.assertEqual(NodeStatus.FAILURE, node.status)

    def _test_generic_rm_not_in_state(self,cls,state):
        node = cls()
        node.bb = ActorState()

        for rm_state in RM:
            node.bb.q_rm = rm_state

            node.tick()

            if rm_state != state:
                # success when they disagree
                self.assertEqual(NodeStatus.SUCCESS, node.status)
            else:
                # failure when they agree
                self.assertEqual(NodeStatus.FAILURE, node.status)

    def test_rm_in_state_start(self):
        self._test_generic_rm_in_state(rmc.RMinStateStart, RM.START)

    def test_rm_in_state_closed(self):
        self._test_generic_rm_in_state(rmc.RMinStateClosed, RM.CLOSED)

    def test_rm_in_state_received(self):
        self._test_generic_rm_in_state(rmc.RMinStateReceived, RM.RECEIVED)

    def test_rm_in_state_invalid(self):
        self._test_generic_rm_in_state(rmc.RMinStateInvalid, RM.INVALID)

    def test_rm_in_state_valid(self):
        self._test_generic_rm_in_state(rmc.RMinStateValid, RM.VALID)

    def test_rm_in_state_deferred(self):
        self._test_generic_rm_in_state(rmc.RMinStateDeferred, RM.DEFERRED)

    def test_rm_in_state_accepted(self):
        self._test_generic_rm_in_state(rmc.RMinStateAccepted, RM.ACCEPTED)

    def test_rm_not_in_state_start(self):
        self._test_generic_rm_not_in_state(rmc.RMnotInStateStart, RM.START)

    def test_rm_not_in_state_closed(self):
        self._test_generic_rm_not_in_state(rmc.RMnotInStateClosed, RM.CLOSED)

    def _test_generic_multi_state_check(self,cls,states):
        node = cls()
        node.bb = ActorState()

        for rm_state in RM:
            node.bb.q_rm = rm_state

            node.tick()

            if rm_state in states:
                # success when they agree
                self.assertEqual(NodeStatus.SUCCESS, node.status)
            else:
                # failure when they disagree
                self.assertEqual(NodeStatus.FAILURE, node.status)

    def test_rm_in_state_deferred_or_accepted(self):
        self._test_generic_multi_state_check(rmc.RMinStateDeferredOrAccepted, [RM.DEFERRED,RM.ACCEPTED])

    def test_rm_in_state_received_or_invalid(self):
        self._test_generic_multi_state_check(rmc.RMinStateReceivedOrInvalid, [RM.RECEIVED,RM.INVALID])

    def test_rm_in_state_start_or_closed(self):
        self._test_generic_multi_state_check(rmc.RMinStateStartOrClosed, [RM.START,RM.CLOSED])

    def test_rm_in_state_valid_or_deferred_or_accepted(self):
        self._test_generic_multi_state_check(rmc.RMinStateValidOrDeferredOrAccepted, [RM.VALID,RM.DEFERRED,RM.ACCEPTED])




if __name__ == '__main__':
    unittest.main()
