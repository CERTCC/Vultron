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
from enum import Enum

import vultron.case_states.patterns.cvss31 as cvss
from vultron.case_states.hypercube import CVDmodel


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.model = CVDmodel()

    def tearDown(self):
        pass

    def test_cvss_31_e(self):
        for state in self.model.states:
            result = cvss.cvss_31_e(state)
            # result should always be a list of non-zero length of strings of non-zero length
            self.assertIsInstance(result, list)
            for item in result:
                self.assertIsInstance(item, Enum)

    def test_cvss_31_rl(self):
        for state in self.model.states:
            result = cvss.cvss_31_rl(state)
            # result should always be a list of non-zero length of strings of non-zero length
            self.assertIsInstance(result, list)
            for item in result:
                self.assertIsInstance(item, Enum)

    def test_cvss_31(self):
        for state in self.model.states:
            result = cvss.cvss_31(state)
            # result should always be a list of non-zero length of strings of non-zero length
            self.assertIsInstance(result, list)
            for item in result:
                self.assertIsInstance(item, Enum)

    def test_cvss_exploitation_state(self):
        for state in self.model.states:
            result = cvss.cvss_31_e(state)
            # if A in state, then Exploitation: Active should be in result
            if "A" in state:
                self.assertIn(cvss.CVSS_31_E.HIGH, result)
                self.assertIn(cvss.CVSS_31_E.FUNCTIONAL, result)
            elif "X" in state:
                self.assertIn(cvss.CVSS_31_E.HIGH, result)
                self.assertIn(cvss.CVSS_31_E.FUNCTIONAL, result)
                self.assertIn(cvss.CVSS_31_E.PROOF_OF_CONCEPT, result)
            else:
                self.assertIn(cvss.CVSS_31_E.UNPROVEN, result)
                self.assertIn(cvss.CVSS_31_E.NOT_DEFINED, result)

                self.assertNotIn(cvss.CVSS_31_E.PROOF_OF_CONCEPT, result)
                self.assertNotIn(cvss.CVSS_31_E.FUNCTIONAL, result)
                self.assertNotIn(cvss.CVSS_31_E.HIGH, result)


if __name__ == "__main__":
    unittest.main()
