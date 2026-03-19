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
from itertools import product

import vultron.core.states.cs as s


class MyTestCase(unittest.TestCase):
    def setUp(self):
        vfd = ["vfd", "Vfd", "VFd", "VFD"]
        pxa = ["pxa", "Pxa", "pXa", "pxA", "PXa", "pXA", "PxA", "PXA"]

        self.states = [a + b for (a, b) in product(vfd, pxa)]

        self.assertEqual(32, len(self.states))

    def test_state_string_to_enums(self):
        for state_string in self.states:
            vfd, pxa = s.state_string_to_enums(state_string)
            self.assertEqual(state_string[:3], vfd.name)
            self.assertEqual(state_string[3:], pxa.name)

    def test_state_string_to_enum2(self):
        for state_string in self.states:
            result = s.state_string_to_enum2(state_string)
            # for each character in state string, check that the string value matches
            for i, c in enumerate(state_string):
                self.assertEqual(c, str(result[i]))

    def test_CS_vfdpxa(self):
        for state_string in self.states:
            vfd_str = state_string[:3]
            pxa_str = state_string[3:]

            cs = getattr(s.CS, state_string)
            self.assertEqual(state_string, cs.name)

            vfd = getattr(s.CS_vfd, vfd_str)
            self.assertEqual(vfd_str, vfd.name)
            self.assertEqual(vfd, cs.value.vfd_state)
            self.assertEqual(vfd_str, cs.value.vfd_state.name)

            pxa = getattr(s.CS_pxa, pxa_str)
            self.assertEqual(pxa_str, pxa.name)
            self.assertEqual(pxa, cs.value.pxa_state)
            self.assertEqual(pxa_str, cs.value.pxa_state.name)


if __name__ == "__main__":
    unittest.main()
