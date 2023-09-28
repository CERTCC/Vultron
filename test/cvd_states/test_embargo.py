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

import vultron.cvd_states.hypercube as sg
import vultron.cvd_states.patterns.embargo as mb
from vultron.cvd_states.errors import StateValidationError


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.model = sg.CVDmodel()

    def tearDown(self):
        pass

    def test_reject_bogus_states(self):
        funcs = [mb.can_start_embargo, mb.embargo_viable]
        bogus_states = ["abbso", "abs", "absd", "absdx", "absdxa", "absdpxa"]
        for func in funcs:
            for state in bogus_states:
                self.assertRaises(StateValidationError, func, state)

    def test_embargo_viable(self):
        m = self.model

        # walk all the states and check the embargo_viable function
        for state in m.states:
            if "pxa" in state:
                self.assertTrue(mb.embargo_viable(state))
            else:
                self.assertFalse(mb.embargo_viable(state))

    def test_can_start_embargo(self):
        m = self.model

        # walk all the states and check the can_start_embargo function
        for state in m.states:
            if "dpxa" in state:
                self.assertTrue(mb.can_start_embargo(state))
            else:
                self.assertFalse(mb.can_start_embargo(state))


if __name__ == "__main__":
    unittest.main()
