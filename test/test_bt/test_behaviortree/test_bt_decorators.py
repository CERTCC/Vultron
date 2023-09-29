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

import vultron.bt.base.fuzzer as btz
from vultron.bt.base.bt_node import BtNode
from vultron.bt.base.decorators import (
    ForceFailure,
    ForceRunning,
    ForceSuccess,
    Invert,
    RepeatN,
    RepeatUntilFail,
    RetryN,
    RunningIsFailure,
    RunningIsSuccess,
)
from vultron.bt.base.node_status import NodeStatus

succeed = btz.AlwaysSucceed
fail = btz.AlwaysFail
running = btz.AlwaysRunning


class MyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_invert(self):
        expect = {
            succeed: NodeStatus.FAILURE,
            fail: NodeStatus.SUCCESS,
            running: NodeStatus.RUNNING,
        }

        self._check_expected_results(expect, Invert)

    def test_running_is_failure(self):
        expect = {
            succeed: NodeStatus.SUCCESS,
            fail: NodeStatus.FAILURE,
            running: NodeStatus.FAILURE,
        }

        self._check_expected_results(expect, RunningIsFailure)

    def test_running_is_success(self):
        expect = {
            succeed: NodeStatus.SUCCESS,
            fail: NodeStatus.FAILURE,
            running: NodeStatus.SUCCESS,
        }

        self._check_expected_results(expect, RunningIsSuccess)

    def _check_expected_results(self, expect, klass):
        for child, result in expect.items():

            class Cls(klass):
                _children = (child,)

            instance = Cls()
            self.assertEqual(result, instance.tick())

    def test_force_success(self):
        expect = {
            succeed: NodeStatus.SUCCESS,
            fail: NodeStatus.SUCCESS,
            running: NodeStatus.SUCCESS,
        }
        self._check_expected_results(expect, ForceSuccess)

    def test_force_failure(self):
        expect = {
            succeed: NodeStatus.FAILURE,
            fail: NodeStatus.FAILURE,
            running: NodeStatus.FAILURE,
        }
        self._check_expected_results(expect, ForceFailure)

    def test_force_running(self):
        expect = {
            succeed: NodeStatus.RUNNING,
            fail: NodeStatus.RUNNING,
            running: NodeStatus.RUNNING,
        }
        self._check_expected_results(expect, ForceRunning)

    def test_retry_n(self):
        class Retry100(RetryN):
            n = 100
            _children = (fail,)

        parent = Retry100()
        self.assertEqual(0, parent.count)
        parent.tick()
        self.assertEqual(parent.n, parent.count)
        parent.tick()
        self.assertEqual(2 * parent.n, parent.count)
        parent.tick()
        self.assertEqual(3 * parent.n, parent.count)

        # counter resets every time
        parent.reset = True
        parent.tick()
        self.assertEqual(parent.n, parent.count)

    def test_repeat_n(self):
        for _n in range(1, 100):

            class Repeat_n(RepeatN):
                n = _n
                _children = (succeed,)

            parent = Repeat_n()
            self.assertEqual(0, parent.count)
            parent.tick()
            self.assertEqual(parent.n, parent.count)
            parent.tick()
            self.assertEqual(2 * parent.n, parent.count)
            parent.tick()
            self.assertEqual(3 * parent.n, parent.count)

            # counter resets every time
            parent.reset = True
            parent.tick()
            self.assertEqual(parent.n, parent.count)

    def test_repeat_until_fail(self):
        for n in range(1, 100):

            class WinBeforeLose(BtNode):
                # dummy class that succeeds n times before failure
                i = 0

                def _tick(self, depth=0):
                    self.i += 1
                    if self.i < n:
                        return NodeStatus.SUCCESS
                    return NodeStatus.FAILURE

            class UntilFail(RepeatUntilFail):
                _children = (WinBeforeLose,)

            parent = UntilFail()
            self.assertEqual(0, parent.count)
            parent.tick()
            self.assertEqual(n, parent.count)


if __name__ == "__main__":
    unittest.main()
