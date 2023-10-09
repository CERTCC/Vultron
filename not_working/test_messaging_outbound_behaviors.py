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
from dataclasses import dataclass, field
from typing import Callable, List

from vultron.sim.communications import Message

from vultron.bt.messaging.outbound.behaviors import EmitMsg, Emitters


@dataclass
class MockState:
    emit_func: Callable = None
    sender: str = None
    msg_history: List[str] = field(default_factory=list)
    msgs_emitted_this_tick: List[str] = field(default_factory=list)
    incoming_messages: List[str] = field(default_factory=list)
    name: str = "foo"


class TestEmitMsg(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_init(self):
        em = EmitMsg()
        self.assertIn(em.name_pfx, em.name)
        self.assertIn(em.__class__.__name__, em.name)
        self.assertIn(str(em.__class__.msg_type), em.name)
        self.assertEqual(em.__class__.msg_type, em.msg_type)

    def _test_emmitter(self, emitter_cls):
        em = emitter_cls()

        em.bb = MockState()

        # we need a dummy emit function to receive messages
        messages = []

        def emitfunc(msg):
            messages.append(msg)

        em.bb.emit_func = emitfunc
        em.bb.sender = "TestSender"

        em._tick()

        self.assertGreater(
            len(messages), 0, "Expected non-empty list of messages emitted"
        )
        for msg in messages:
            self.assertIsInstance(msg, Message)
            self.assertEqual(em.msg_type, msg.msg_type)
            self.assertIn(msg, em.bb.msg_history)
            self.assertIn(msg.msg_type, em.bb.msgs_emitted_this_tick)
            self.assertIn(msg, em.bb.incoming_messages)

    def test_tick(self):
        # Emitters is a list of all the subclasses of EmitMsg
        # that are created in vultron.bt.messaging.outbount.behaviors
        for emitter_cls in Emitters:
            self._test_emmitter(emitter_cls)


if __name__ == "__main__":
    unittest.main()
