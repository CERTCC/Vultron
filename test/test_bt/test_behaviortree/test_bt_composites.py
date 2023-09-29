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

import vultron.bt.base.composites as composites
import vultron.bt.base.fuzzer as btz
from vultron.bt.base.node_status import NodeStatus

fail = btz.AlwaysFail
succeed = btz.AlwaysSucceed
running = btz.AlwaysRunning


class TestComposites(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _children_match_expected(self, expect, klass):
        # Test that the children of the given class match the expected results
        # for the given expect dictionary of (children, result) pairs where the children are tuples of nodes
        for children, result in expect.items():

            class Cls(klass):
                _children = children

            instance = Cls()
            self.assertEqual(result, instance.tick())

    def test_sequence(self):
        # SequenceNode should return the first failure, or success if all succeed
        expect = {
            (fail, fail): NodeStatus.FAILURE,
            (fail, succeed): NodeStatus.FAILURE,
            (fail, running): NodeStatus.FAILURE,
            (succeed, fail): NodeStatus.FAILURE,
            (succeed, succeed): NodeStatus.SUCCESS,
            (succeed, running): NodeStatus.RUNNING,
            (running, fail): NodeStatus.RUNNING,
            (running, succeed): NodeStatus.RUNNING,
            (running, running): NodeStatus.RUNNING,
        }

        self._children_match_expected(expect, composites.SequenceNode)

    def test_fallback(self):
        # FallbackNode should return the first success, or failure if all fail
        expect = {
            (fail, fail): NodeStatus.FAILURE,
            (fail, succeed): NodeStatus.SUCCESS,
            (fail, running): NodeStatus.RUNNING,
            (succeed, fail): NodeStatus.SUCCESS,
            (succeed, succeed): NodeStatus.SUCCESS,
            (succeed, running): NodeStatus.SUCCESS,
            (running, fail): NodeStatus.RUNNING,
            (running, succeed): NodeStatus.RUNNING,
            (running, running): NodeStatus.RUNNING,
        }

        self._children_match_expected(expect, composites.FallbackNode)

    def test_parallel(self):
        # todo: test parallel node
        pass


if __name__ == "__main__":
    unittest.main()
