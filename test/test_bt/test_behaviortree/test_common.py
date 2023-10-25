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

import logging
import unittest
from itertools import product

from vultron.bt import common as c
from vultron.bt.base.composites import FallbackNode
from vultron.bt.base.node_status import NodeStatus

logger = logging.getLogger()

logger.addHandler(logging.StreamHandler())


# logger.setLevel(logging.DEBUG)


class MockState:
    foo = 0
    foo_history = []


class MyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_to_end_state_factory(self):
        bb = MockState()

        for key, state in product("abcdefghij", range(10)):
            xclass = c.to_end_state_factory(key, state)
            self.assertTrue(callable(xclass))

            x = xclass()
            self.assertIn(key, x.name)
            self.assertIn(str(state), x.name)

            setattr(bb, key, 99999)
            histkey = f"{key}_history"
            setattr(bb, histkey, [])
            x.bb = bb

            self.assertEqual(99999, getattr(x.bb, key))
            result = x.tick()
            self.assertEqual(NodeStatus.SUCCESS, result)
            self.assertEqual(state, getattr(x.bb, key))
            self.assertIn(state, getattr(x.bb, histkey))

    def test_make_check_state(self):
        bb = MockState()

        for key, state in product("abcdefghij", range(10)):
            xclass = c.state_in(key, state)
            self.assertTrue(callable(xclass))

            x = xclass()
            self.assertIn(key, x.name)
            self.assertIn(str(state), x.name)

            x.bb = bb
            # check that it returns false / FAILURE when false
            setattr(bb, key, 99999)
            self.assertFalse(x.func())
            self.assertEqual(NodeStatus.FAILURE, x.tick())

            # check that it returns true / SUCCESS when true
            setattr(bb, key, state)
            self.assertTrue(x.func())
            self.assertEqual(NodeStatus.SUCCESS, x.tick())

    def test_make_state_change(self):
        bb = MockState()
        start_states = list(range(5))

        for key, end_state in product("abcdefghij", range(10)):
            with self.subTest(key=key, end_state=end_state):
                transition = c.EnumStateTransition(start_states, end_state)
                xclass = c.make_state_change(key, transition)
                self.assertTrue(callable(xclass))
                self.assertNotEqual("Node", xclass.__name__)
                self.assertIn(key, xclass.__name__)
                x = xclass()

                self.assertTrue(isinstance(x, FallbackNode))
                self.assertIn(key, x.name)
                self.assertIn(str(end_state), x.name)

                x.bb = bb
                x.setup()

                setattr(bb, key, 99999)
                histkey = f"{key}_history"
                setattr(bb, histkey, [])

                result = x.tick()
                self.assertEqual(NodeStatus.FAILURE, result)

                # make sure all the start states are allowed
                for i in range(15):
                    setattr(bb, key, i)
                    result = x.tick()
                    if i in start_states or i == end_state:
                        # node succeeds, transition allowed
                        self.assertEqual(NodeStatus.SUCCESS, result)
                        self.assertEqual(end_state, getattr(bb, key))
                    else:
                        # node fails, transition disallowed, state does not change
                        self.assertEqual(NodeStatus.FAILURE, result)
                        self.assertEqual(i, getattr(bb, key))


if __name__ == "__main__":
    unittest.main()
