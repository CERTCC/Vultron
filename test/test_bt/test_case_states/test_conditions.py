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

import vultron.bt.case_state.conditions as csc
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.states import ActorState
from vultron.case_states.states import CS


class MyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.bb = ActorState()

    def _ab(self, node_cls, expect_true, expect_false):
        node = node_cls()
        node.bb = ActorState()

        for state in CS:
            node.bb.q_cs = state
            self.assertEqual(node.bb.q_cs, state)

            node.tick()

            self.assertEqual(node.bb.q_cs, state)

            if expect_true in state.name:
                self.assertEqual(
                    NodeStatus.SUCCESS,
                    node.status,
                    f"node: {node.name} state: {state.name}",
                )
            elif expect_false in state.name:
                self.assertEqual(
                    NodeStatus.FAILURE, node.status, f"state: {state.name}"
                )

    def test_cs_in_state_vendor_aware(self):
        self._ab(csc.CSinStateVendorAware, "V", "v")
        self._ab(csc.CSinStateVendorUnaware, "v", "V")

    def test_cs_in_state_fix_ready(self):
        self._ab(csc.CSinStateFixReady, "F", "f")
        self._ab(csc.CSinStateFixNotReady, "f", "F")

    def test_cs_in_state_fix_deployed(self):
        self._ab(csc.CSinStateFixDeployed, "D", "d")
        self._ab(csc.CSinStateFixNotDeployed, "d", "D")

    def test_cs_in_state_public_aware(self):
        self._ab(csc.CSinStatePublicAware, "P", "p")
        self._ab(csc.CSinStatePublicUnaware, "p", "P")

    def test_cs_in_state_exploit_public(self):
        self._ab(csc.CSinStateExploitPublic, "X", "x")
        self._ab(csc.CSinStateNoExploitPublic, "x", "X")

    def test_cs_in_state_attacks_observed(self):
        self._ab(csc.CSinStateAttacksObserved, "A", "a")
        self._ab(csc.CSinStateNoAttacksObserved, "a", "A")


    def test_combo_checks(self):
        # PX
        # VF
        # VFD
        # pxa
        # PXA
        # dpxa
        # dP
        # VFd
        pass


if __name__ == "__main__":
    unittest.main()
