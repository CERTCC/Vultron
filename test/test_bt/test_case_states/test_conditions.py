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


def all_casings(input_string):
    if not input_string:
        yield ""
    else:
        first = input_string[:1]
        if first.lower() == first.upper():
            for sub_casing in all_casings(input_string[1:]):
                yield first + sub_casing
        else:
            for sub_casing in all_casings(input_string[1:]):
                yield first.lower() + sub_casing
                yield first.upper() + sub_casing


class MyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.bb = ActorState()

    def _ab(
        self, node_cls: object, expect_true_when: str, extra: list = []
    ) -> None:
        """
        Abstracts out the test for a CS state condition node

        Args:
            node_cls: The bt condition node to test
            expect_true_when: a string that should appear in the state name if the condition is true
            extra: a list of other strings that might also cause the condition to resolve to true

        """

        node = node_cls()
        node.bb = self.bb

        for state in CS:
            node.bb.q_cs = state
            self.assertEqual(node.bb.q_cs, state)

            # do the thing
            node.tick()

            self.assertEqual(node.bb.q_cs, state)

            if expect_true_when in state.name or any(
                [x in state.name for x in extra]
            ):
                self.assertEqual(
                    NodeStatus.SUCCESS,
                    node.status,
                    f"{node.name} expected SUCCESS on state:{state.name}",
                )
                continue

            # for each letter in expect_true, generate all the other case permutations and check for failure
            casings = list(all_casings(expect_true_when))
            casings.remove(expect_true_when)
            self.assertNotIn(expect_true_when, casings)

            for s in casings:
                if s not in state.name:
                    continue

                if any([x in state.name for x in extra]):
                    continue

                print(s, state.name)
                # if s in state.name:
                self.assertEqual(
                    NodeStatus.FAILURE,
                    node.status,
                    f"{node.name} expected FAILURE on state:{state.name}",
                )

    def test_cs_in_state_vendor_aware(self):
        self._ab(node_cls=csc.CSinStateVendorAware, expect_true_when="V")

    def test_cs_in_state_vendor_unaware(self):
        self._ab(node_cls=csc.CSinStateVendorUnaware, expect_true_when="v")

    def test_cs_in_state_fix_ready(self):
        self._ab(node_cls=csc.CSinStateFixReady, expect_true_when="F")

    def test_cs_in_state_fix_not_ready(self):
        self._ab(node_cls=csc.CSinStateFixNotReady, expect_true_when="f")

    def test_cs_in_state_fix_deployed(self):
        self._ab(node_cls=csc.CSinStateFixDeployed, expect_true_when="D")

    def test_cs_in_state_fix_not_deployed(self):
        self._ab(node_cls=csc.CSinStateFixNotDeployed, expect_true_when="d")

    def test_cs_in_state_public_aware(self):
        self._ab(node_cls=csc.CSinStatePublicAware, expect_true_when="P")

    def test_cs_in_state_public_unaware(self):
        self._ab(node_cls=csc.CSinStatePublicUnaware, expect_true_when="p")

    def test_cs_in_state_exploit_public(self):
        self._ab(node_cls=csc.CSinStateExploitPublic, expect_true_when="X")

    def test_cs_in_state_no_exploit_public(self):
        self._ab(node_cls=csc.CSinStateNoExploitPublic, expect_true_when="x")

    def test_cs_in_state_attacks_observed(self):
        self._ab(node_cls=csc.CSinStateAttacksObserved, expect_true_when="A")

    def test_cs_in_state_no_attacks_observed(self):
        self._ab(node_cls=csc.CSinStateNoAttacksObserved, expect_true_when="a")

    def test_PX_combo(self):
        self._ab(
            node_cls=csc.CSinStatePublicAwareAndExploitPublic,
            expect_true_when="PX",
        )

    def test_VF_combo(self):
        self._ab(
            node_cls=csc.CSinStateVendorAwareAndFixReady, expect_true_when="VF"
        )

    def test_VFD_combo(self):
        self._ab(
            node_cls=csc.CSinStateVendorAwareAndFixReadyAndFixDeployed,
            expect_true_when="VFD",
        )

    def test_pxa_combo(self):
        self._ab(
            node_cls=csc.CSinStateNotPublicNoExploitNoAttacks,
            expect_true_when="pxa",
        )

    def test_P_or_X_or_A_combo_P(self):
        self._ab(
            node_cls=csc.CSinStatePublicAwareOrExploitPublicOrAttacksObserved,
            expect_true_when="P",
            extra=["X", "A"],
        )

    def test_P_or_X_or_A_combo_X(self):
        self._ab(
            node_cls=csc.CSinStatePublicAwareOrExploitPublicOrAttacksObserved,
            expect_true_when="X",
            extra=["P", "A"],
        )

    def test_P_or_X_or_A_combo_A(self):
        self._ab(
            node_cls=csc.CSinStatePublicAwareOrExploitPublicOrAttacksObserved,
            expect_true_when="A",
            extra=["P", "X"],
        )

    def test_dpxa_combo(self):
        self._ab(
            node_cls=csc.CSinStateNotDeployedNotPublicNoExploitNoAttacks,
            expect_true_when="dpxa",
        )

    def test_dP_combo(self):
        self._ab(
            node_cls=csc.CSinStateNotDeployedButPublicAware,
            expect_true_when="dP",
        )

    def test_VFd_combo(self):
        self._ab(
            node_cls=csc.CSinStateVendorAwareFixReadyFixNotDeployed,
            expect_true_when="VFd",
        )


if __name__ == "__main__":
    unittest.main()
