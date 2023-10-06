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

import vultron.bt.base.fuzzer as btz
from vultron.bt.base import bt
from vultron.bt.base.bt_node import BtNode, ConditionCheck, CountTicks
from vultron.bt.base.node_status import NodeStatus


class MockState(dict):
    pass


def func_true():
    return True


def func_false():
    return False


class MyTestCase(unittest.TestCase):
    def setUp(self):
        # reset the object counter
        BtNode._objcount = 0

    def tearDown(self):
        pass

    def test_ConditionCheck2(self):
        cc = ConditionCheck()
        cc.bb = MockState()

        cc.func = func_true
        result = cc._tick()
        self.assertEqual(NodeStatus.SUCCESS, result)

        cc.func = func_false
        result = cc._tick()
        self.assertEqual(NodeStatus.FAILURE, result)

    def test_add_child(self):
        parent = BtNode()
        child = BtNode()

        self.assertEqual(None, child.parent)
        self.assertNotIn(child, parent.children)
        parent.add_child(child)
        self.assertEqual(parent, child.parent)
        self.assertIn(child, parent.children)
        self.assertEqual(child.indent_level, parent.indent_level + 1)

    def test_state_follows_parent(self):
        parent = BtNode()
        child = BtNode()
        parent.bb = MockState()

        self.assertTrue(isinstance(parent.bb, MockState))
        self.assertFalse(isinstance(child.bb, MockState))
        parent.add_child(child)
        self.assertTrue(isinstance(parent.bb, MockState))
        self.assertTrue(isinstance(child.bb, MockState))
        self.assertEqual(parent.bb, child.bb)

    def test_setup(self):
        class MyTree(bt.BehaviorTree):
            bbclass = MockState

        tree = MyTree()
        root = BtNode()

        n = 10
        root._children = [BtNode for _ in range(10)]

        self.assertEqual(0, len(root.children))
        root.add_children()
        self.assertEqual(n, len(root.children))

        self.assertIsInstance(tree.bb, MockState)

        tree.bb.foo = True
        self.assertTrue(hasattr(tree.bb, "foo"))
        self.assertTrue(tree.bb.foo)

        tree.add_root(root)

        # only root should get the blackboard so far
        self.assertIsInstance(root.bb, MockState)
        self.assertTrue(hasattr(root.bb, "foo"))
        self.assertTrue(root.bb.foo)

        for node in root.children:
            self.assertIsNone(node.bb)
            self.assertFalse(hasattr(node.bb, "foo"))

        tree.setup()

        # now everything should have it
        for node in root.children:
            self.assertIsInstance(node.bb, MockState)
            self.assertEqual(tree.bb, node.bb)
            self.assertTrue(hasattr(node.bb, "foo"))
            self.assertTrue(node.bb.foo)

    def test_add_children(self):
        parent = BtNode()
        n = 10
        children = [BtNode for i in range(n)]

        self.assertFalse(parent.children)
        parent._children = children
        parent.add_children()
        self.assertEqual(n, len(parent.children))

        for child_cls, child_inst in zip(children, parent.children):
            self.assertIsInstance(child_inst, child_cls)
            self.assertEqual(child_inst.indent_level, parent.indent_level + 1)

    def test_count_ticks(self):
        c = CountTicks()
        for i in range(1000):
            self.assertEqual(i, c.counter)
            c.tick()

        c = CountTicks()
        c.counter = 374
        for i in range(374, 450):
            self.assertEqual(i, c.counter)
            c.tick()

    def test_always_succeed(self):
        s = btz.AlwaysSucceed()
        for i in range(1000):
            self.assertEqual(NodeStatus.SUCCESS, s.tick())

    def test_always_fail(self):
        s = btz.AlwaysFail()
        for i in range(1000):
            self.assertEqual(NodeStatus.FAILURE, s.tick())

    def test_always_running(self):
        s = btz.AlwaysRunning()
        for i in range(1000):
            self.assertEqual(NodeStatus.RUNNING, s.tick())

    def test_btnode_objcount(self):
        # We expect that there is exactly one _objcount shared across all
        # subclasses of BtNode. This test creates a bunch of BtNodes and checks
        # that the _objcount is incremented correctly.

        n = 100
        self.assertEqual(0, BtNode._objcount)
        for i in range(n):
            self.assertEqual(i, BtNode._objcount)
            BtNode()
            self.assertEqual(i + 1, BtNode._objcount)

    def test_btnode_objcount_subclasses(self):
        # We expect that there is exactly one _objcount shared across all
        # subclasses of BtNode. This test creates a nested set of subclasses of
        # BtNode and checks that the _objcount is incremented correctly.
        def subclass(cls):
            class Foo(cls):
                pass

            return Foo

        depth = 100  # this is way deeper than we probably ever need to go
        self.assertEqual(0, BtNode._objcount)
        subcls = subclass(BtNode)
        for i in range(depth):
            self.assertEqual(i, BtNode._objcount)
            # instantiate it
            subcls()
            self.assertEqual(i + 1, BtNode._objcount)

            # go one deeper
            subcls = subclass(subcls)

        self.assertEqual(depth, BtNode._objcount)


if __name__ == "__main__":
    unittest.main()
