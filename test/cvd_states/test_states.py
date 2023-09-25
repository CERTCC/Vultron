import unittest
from itertools import product

import vultron.cvd_states.states as states


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

            (s1, s2, s3) = s
            (p, x, a) = attrib.value

            # check that the values are correct
            self.assertEqual(getattr(states.PublicAwareness, s1), p)
            self.assertEqual(getattr(states.ExploitPublication, s2), x)
            self.assertEqual(getattr(states.AttackObservation, s3), a)

    def test_cs_vfd(self):
        for vfd in ("vfd", "Vfd", "VFd", "VFD"):
            attrib = getattr(states.CS_vfd, vfd)
            self.assertEqual(vfd, attrib.name)

            (s1, s2, s3) = vfd
            (v, f, d) = attrib.value

            # check that the values are correct
            self.assertEqual(getattr(states.VendorAwareness, s1), v)
            self.assertEqual(getattr(states.FixReadiness, s2), f)
            self.assertEqual(getattr(states.FixDeployment, s3), d)


if __name__ == "__main__":
    unittest.main()
