#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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
from collections import deque

from pydantic import BaseModel

from vultron.bt.base.bt_node import ActionNode
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.messaging.inbound._behaviors.common import (
    LogMsg,
    PopMessage,
    PushMessage,
    UnsetCurrentMsg,
)


class MockState:
    current_message = None
    incoming_messages = deque()
    msgs_received_this_tick = []


class MockMsg(BaseModel):
    msg_type: str = "gloop"


class MyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_pop_message_fails_if_current_message_set(self):
        pm = PopMessage()
        self.assertIsInstance(pm, ActionNode)

        # fail if current_message is already set
        pm.bb = MockState()
        pm.bb.current_message = 1
        self.assertIsNotNone(pm.bb.current_message)
        self.assertEqual(NodeStatus.FAILURE, pm._tick())

    def test_pop_message_fails_when_incoming_empty(self):
        pm = PopMessage()
        self.assertIsInstance(pm, ActionNode)

        pm.bb = MockState()
        self.assertIsNone(pm.bb.current_message)
        # incoming messages is a deque
        # empty deque evaluates as False
        self.assertFalse(pm.bb.incoming_messages)
        # ticking pm must therefore fail
        self.assertEqual(NodeStatus.FAILURE, pm._tick())

    def test_pop_message_succeeds(self):
        pm = PopMessage()
        self.assertIsInstance(pm, ActionNode)

        msg = MockMsg()
        pm.bb = MockState()
        pm.bb.incoming_messages.append(msg)
        self.assertIsNone(pm.bb.current_message)
        # incoming messages is a deque
        r = pm._tick()

        # check for success
        self.assertEqual(NodeStatus.SUCCESS, r)

        # check post-conditions
        # message is now current message
        self.assertEqual(msg, pm.bb.current_message)

    def test_pop_message_fifo(self):
        pm = PopMessage()
        pm.bb = MockState()

        # test FIFO
        messages = [MockMsg(msg_type=x) for x in "abcdefg"]
        pm.bb.incoming_messages.extend(messages)
        for msg in messages:
            pm.bb.current_message = None

            r = pm._tick()
            self.assertEqual(NodeStatus.SUCCESS, r)
            self.assertEqual(msg, pm.bb.current_message)

    def test_push_message_succeeds_if_no_current_message(self):
        pm = PushMessage()
        pm.bb = MockState()

        self.assertIsNone(pm.bb.current_message)
        r = pm._tick()
        self.assertEqual(NodeStatus.SUCCESS, r)

    def test_push_message_succeeds_if_current_message(self):
        pm = PushMessage()
        pm.bb = MockState()

        self.assertIsNone(pm.bb.current_message)
        self.assertEqual(len(pm.bb.incoming_messages), 0)

        messages = list("abcdefghijklmnopqrstuvwxyz")

        for msg in messages:
            pm.bb.current_message = msg
            r = pm._tick()
            self.assertEqual(NodeStatus.SUCCESS, r)
            self.assertIsNone(pm.bb.current_message)
        self.assertEqual(
            len(pm.bb.incoming_messages),
            len(messages),
            pm.bb.incoming_messages,
        )

        # push message puts it back on the queue for next time
        messages.reverse()
        for msg in messages:
            m = pm.bb.incoming_messages.popleft()
            self.assertEqual(msg, m)

        self.assertEqual(
            len(pm.bb.incoming_messages), 0, pm.bb.incoming_messages
        )

    def test_unset_current_msg(self):
        node = UnsetCurrentMsg()
        node.bb = MockState()
        msg = MockMsg()
        self.assertIsNone(node.bb.current_message)
        node.bb.current_message = msg
        self.assertEqual(msg, node.bb.current_message)

        self.assertIsNone(node.status)

        node.tick()

        self.assertEqual(NodeStatus.SUCCESS, node.status)
        self.assertIsNone(node.bb.current_message)

    def test_log_msg(self):
        node = LogMsg()
        node.bb = MockState()
        msg = MockMsg()
        self.assertIsNone(node.bb.current_message)
        node.bb.current_message = msg
        self.assertEqual(msg, node.bb.current_message)

        self.assertEqual(0, len(node.bb.msgs_received_this_tick))
        self.assertIsNone(node.status)

        node.tick()

        # node should succeed
        self.assertEqual(NodeStatus.SUCCESS, node.status)
        # current message should not change
        self.assertEqual(msg, node.bb.current_message)
        # but the message type should be logged
        self.assertEqual(1, len(node.bb.msgs_received_this_tick))
        self.assertEqual(msg.msg_type, node.bb.msgs_received_this_tick[-1])


if __name__ == "__main__":
    unittest.main()
