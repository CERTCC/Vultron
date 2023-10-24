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
from itertools import product

import vultron.bt.messaging.inbound._behaviors.cs_messages as vmc
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.messaging.states import MessageTypes as MT
from vultron.case_states.states import CS


class MockMsg:
    msg_type: MT = None


class MockState:
    current_message: MockMsg = None
    q_cs: CS = None
    name: str = "Foo"
    emit_func: callable = lambda *x: None
    msg_history: list = []
    msgs_emitted_this_tick: list = []
    incoming_messages: list = []


class MyTestCase(unittest.TestCase):
    def test_handle_cp_ca(self):
        """
        Test that the _HandleCp and _HandleCa nodes transition to the correct state based on the current message type
        and the current case state.
        """
        for expect_success_on, cls, pattern in zip(
            [MT.CP, MT.CA],
            [vmc._HandleCp, vmc._HandleCa],
            ["...P..", ".....A"],
        ):
            for msg_type, q_cs in product(MT, CS):
                with self.subTest(
                    cls=cls,
                    msg_type=msg_type,
                    q_cs=q_cs,
                    expect_success_on=expect_success_on,
                    pattern=pattern,
                ):
                    # setup the node
                    node = cls()
                    node.bb = MockState()

                    msg = MockMsg()
                    msg.msg_type = msg_type
                    node.bb.current_message = msg
                    node.bb.q_cs = q_cs

                    self.assertIsNone(node.status)

                    node.tick()

                    if node.bb.current_message.msg_type == expect_success_on:
                        self.assertEqual(NodeStatus.SUCCESS, node.status)
                        self.assertRegex(node.bb.q_cs.name, pattern)
                    else:
                        self.assertEqual(NodeStatus.FAILURE, node.status)
                        self.assertEqual(q_cs, node.bb.q_cs)

    def test_handle_cx(self):
        """
        Test that the _HandleCx node transitions to the correct state based on the current message type and the current
        case state.
        """
        cls = vmc._HandleCx
        expect_success_on = MT.CX
        pattern = "...PX."  # pX is not usually valid because X implies P so we should see a transition to P as well

        for msg_type, q_cs in product(MT, CS):
            with self.subTest(
                cls=cls,
                msg_type=msg_type,
                q_cs=q_cs,
                expect_success_on=expect_success_on,
                pattern=pattern,
            ):
                # setup the node
                node = cls()
                node.bb = MockState()

                msg = MockMsg()
                msg.msg_type = msg_type
                node.bb.current_message = msg
                node.bb.q_cs = q_cs

                self.assertIsNone(node.status)

                node.tick()

                if node.bb.current_message.msg_type == expect_success_on:
                    self.assertEqual(NodeStatus.SUCCESS, node.status)
                    self.assertRegex(node.bb.q_cs.name, pattern)
                else:
                    self.assertEqual(NodeStatus.FAILURE, node.status)
                    self.assertEqual(q_cs, node.bb.q_cs)

    def test_handle_cv_cf_cd(self):
        """
        Test that the _HandleCv, _HandleCf, and HandleCd nodes do not transition states.
        """
        for expect_success_on, cls in zip(
            [MT.CV, MT.CF, MT.CD],
            [vmc._HandleCv, vmc._HandleCf, vmc._HandleCd],
        ):
            for msg_type, q_cs in product(MT, CS):
                with self.subTest(
                    cls=cls,
                    msg_type=msg_type,
                    q_cs=q_cs,
                    expect_success_on=expect_success_on,
                ):
                    # setup the node
                    node = cls()
                    node.bb = MockState()

                    msg = MockMsg()
                    msg.msg_type = msg_type
                    node.bb.current_message = msg
                    node.bb.q_cs = q_cs

                    self.assertIsNone(node.status)

                    node.tick()

                    # CV doesn't change the case state
                    self.assertEqual(q_cs, node.bb.q_cs)

                    if node.bb.current_message.msg_type == expect_success_on:
                        self.assertEqual(NodeStatus.SUCCESS, node.status)
                    else:
                        self.assertEqual(NodeStatus.FAILURE, node.status)


if __name__ == "__main__":
    unittest.main()
