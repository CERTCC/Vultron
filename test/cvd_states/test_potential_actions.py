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

from vultron.cvd_states.hypercube import CVDmodel
from vultron.cvd_states.patterns import potential_actions as pa


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.model = CVDmodel()
        pass

    def tearDown(self):
        pass

    def test_pa_action(self):
        for state in self.model.states:
            result = pa.action(state)
            # actions should be a list
            self.assertIsInstance(result, list)
            # actions should be non-empty
            self.assertGreater(len(result), 0)
            # actions should be a list of enums
            for a in result:
                self.assertIsInstance(a, pa.Actions)
            # actions should be unique
            self.assertEqual(len(result), len(set(result)))


if __name__ == "__main__":
    unittest.main()
