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

import vultron.case_states.patterns.info as info
from vultron.case_states.hypercube import CVDmodel


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.model = CVDmodel()

    def tearDown(self):
        pass

    def test_info(self):
        for state in self.model.states:
            result = info.info(state)
            # result should always be a list of non-zero length of strings of non-zero length
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            for item in result:
                self.assertIsInstance(item, Enum)


if __name__ == "__main__":
    unittest.main()
