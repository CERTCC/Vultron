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

import vultron.case_states.states as states


class MyTestCase(unittest.TestCase):
    def test_last3(self):
        self.assertEqual("abc", states._last3("wxyabc"))
        self.assertEqual("abc", states._last3("abc"))

    def test_pxa(self):
        for pfx in ("vfd", "Vfd", "VFd", "VFD"):
            for lst in product("pP", "xX", "aA"):
                pxa = "".join(lst)
                state = pfx + pxa
                self.assertEqual(states.CS_pxa[pxa].value, states.pxa(state))

    def test_cs_pxa(self):
        for s in product("pP", "xX", "aA"):
            pxa = "".join(s)
            attrib = getattr(states.CS_pxa, pxa)
            self.assertEqual(pxa, attrib.name)

            s1, s2, s3 = s
            p, x, a = attrib.value

            # check that the values are correct
            self.assertEqual(getattr(states.PublicAwareness, s1), p)
            self.assertEqual(getattr(states.ExploitPublication, s2), x)
            self.assertEqual(getattr(states.AttackObservation, s3), a)

    def test_cs_vfd(self):
        for vfd in ("vfd", "Vfd", "VFd", "VFD"):
            attrib = getattr(states.CS_vfd, vfd)
            self.assertEqual(vfd, attrib.name)

            s1, s2, s3 = vfd
            v, f, d = attrib.value

            # check that the values are correct
            self.assertEqual(getattr(states.VendorAwareness, s1), v)
            self.assertEqual(getattr(states.FixReadiness, s2), f)
            self.assertEqual(getattr(states.FixDeployment, s3), d)


if __name__ == "__main__":
    unittest.main()
