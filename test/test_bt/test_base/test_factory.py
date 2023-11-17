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

from vultron.bt.base.bt_node import ActionNode, BtNode, ConditionCheck
from vultron.bt.base.composites import FallbackNode, ParallelNode, SequenceNode
from vultron.bt.base.decorators import Invert, RepeatUntilFail
from vultron.bt.base.factory import (
    action_node,
    condition_check,
    fallback_node,
    fuzzer,
    invert,
    node_factory,
    parallel_node,
    repeat_until_fail,
    sequence_node,
)
from vultron.bt.base.fuzzer import FuzzerNode, WeightedSuccess


class MyTestCase(unittest.TestCase):
    def setUp(self):
        children = []
        for i in range(3):
            name = f"node{i}"
            docstr = f"docstr{i}"
            child = type(name, (BtNode,), {})
            child.__doc__ = docstr
            children.append(child)
        self.children = children

    def test_node_factory(self):
        for node_cls in [
            BtNode,
            ActionNode,
            ConditionCheck,
            FallbackNode,
            ParallelNode,
            SequenceNode,
            Invert,
            RepeatUntilFail,
            FuzzerNode,
        ]:
            name = "foo"
            docstr = "bar"

            children = []

            node = node_factory(node_cls, name, docstr, children)

            # test that node is a subclass of node_cls
            self.assertTrue(issubclass(node, node_cls))
            self.assertEqual(name, node.__name__)
            self.assertEqual(docstr, node.__doc__)

            # can't test for instantiation here because some classes have requirements
            # we haven't met yet. We'll do those in the individual tests below.

    def test_sequence(self):
        for x in range(2):
            # throw an error if less than two children
            self.assertRaises(
                ValueError, sequence_node, "foo", "bar", *self.children[:x]
            )

        node_cls = sequence_node("foo", "bar", *self.children)

        self.assertTrue(issubclass(node_cls, SequenceNode))
        self.assertEqual("foo", node_cls.__name__)
        self.assertEqual("bar", node_cls.__doc__)
        self.assertEqual(tuple(self.children), node_cls._children)

        self.assertIsInstance(node_cls(), node_cls)

    def test_fallback(self):
        for x in range(1):
            # throw an error if less than one child
            self.assertRaises(
                ValueError, fallback_node, "foo", "bar", *self.children[:x]
            )

        node_cls = fallback_node("foo", "bar", *self.children)

        self.assertTrue(issubclass(node_cls, FallbackNode))
        self.assertEqual("foo", node_cls.__name__)
        self.assertEqual("bar", node_cls.__doc__)
        self.assertEqual(tuple(self.children), node_cls._children)

        self.assertIsInstance(node_cls(), node_cls)

    def test_invert(self):
        # invert should only take one child
        self.assertGreater(len(self.children), 1)
        self.assertRaises(ValueError, invert, "foo", "bar", *self.children)

        # so let's just use the first child
        children = [
            self.children[0],
        ]
        node_cls = invert("foo", "bar", *children)

        self.assertTrue(issubclass(node_cls, Invert))
        self.assertEqual("foo", node_cls.__name__)
        self.assertEqual("bar", node_cls.__doc__)
        self.assertEqual(tuple(children), node_cls._children)

        self.assertIsInstance(node_cls(), node_cls)

    def test_fuzzer(self):
        node_cls = fuzzer(WeightedSuccess, "foo", "bar")

        self.assertTrue(issubclass(node_cls, FuzzerNode))
        self.assertEqual("foo", node_cls.__name__)
        self.assertEqual("bar", node_cls.__doc__)

        self.assertIsInstance(node_cls(), node_cls)

    def test_condition_check(self):
        func = lambda: True
        func.__doc__ = "bar"
        node_cls = condition_check("foo", func)

        self.assertTrue(issubclass(node_cls, ConditionCheck))
        self.assertEqual("foo", node_cls.__name__)
        self.assertEqual("bar", node_cls.__doc__)
        self.assertEqual(func, node_cls.func)

        self.assertIsInstance(node_cls(), node_cls)

    def test_action_node(self):
        func = lambda: True
        func.__doc__ = "bar"
        node_cls = action_node("foo", func)

        self.assertTrue(issubclass(node_cls, ActionNode))
        self.assertEqual("foo", node_cls.__name__)
        self.assertEqual("bar", node_cls.__doc__)

        self.assertIsInstance(node_cls(), node_cls)

    def test_repeat_until_fail(self):
        self.assertGreater(len(self.children), 1)
        self.assertRaises(
            ValueError, repeat_until_fail, "foo", "bar", *self.children
        )

        # so let's just use the first child
        children = [
            self.children[0],
        ]
        node_cls = repeat_until_fail("foo", "bar", *children)

        self.assertTrue(issubclass(node_cls, RepeatUntilFail))
        self.assertEqual("foo", node_cls.__name__)
        self.assertEqual("bar", node_cls.__doc__)
        self.assertEqual(tuple(children), node_cls._children)

        self.assertIsInstance(node_cls(), node_cls)

    def test_parallel_node(self):
        self.assertGreater(len(self.children), 1)
        for x in range(2):
            # throw an error if less than two children
            self.assertRaises(
                ValueError, parallel_node, "foo", "bar", 1, *self.children[:x]
            )

        bad_values = [0, -1, None, "foo", len(self.children) + 1]
        for min_success in bad_values:
            self.assertRaises(
                ValueError,
                parallel_node,
                "foo",
                "bar",
                min_success,
                *self.children,
            )

        # no empty children
        self.assertRaises(ValueError, parallel_node, "foo", "bar", 1, *[])

        for m in range(1, len(self.children) + 1):
            node_cls = parallel_node("foo", "bar", m, *self.children)

            self.assertTrue(issubclass(node_cls, ParallelNode))
            self.assertEqual("foo", node_cls.__name__)
            self.assertEqual("bar", node_cls.__doc__)
            self.assertEqual(tuple(self.children), node_cls._children)

            self.assertIsInstance(node_cls(), node_cls)


if __name__ == "__main__":
    unittest.main()
