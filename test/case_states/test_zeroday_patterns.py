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

import vultron.case_states.patterns.zerodays as zd
from vultron.case_states.hypercube import CVDmodel

not_zero_day_states = [
    "Vfdpxa",
    "VFdpxa",
    "VFdPxa",
    "VFdPxA",
    "VFdPXa",
    "VFdPXA",
    "VFDpxa",
    "VFDPxa",
    "VFDPxA",
    "VFDPXa",
    "VFDPXA",
]

not_zero_day_histories = [
    "VFPAXD",
    "VFPADX",
    "VFPXAD",
    "VFPXDA",
    "VFPDAX",
    "VFPDXA",
    "VFDPAX",
    "VFDPXA",
]


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.sg = CVDmodel()

    def tearDown(self):
        pass

    def test_zeroday_type(self):
        for state in self.sg.states:
            result = zd.zeroday_type(state)
            # should be a list
            self.assertIsInstance(result, list)
            if state in not_zero_day_states:
                # should be n
                self.assertEqual(len(result), 1)
                self.assertIn(zd.ZeroDayType.NOT_APPLICABLE, result)
            else:
                # should be non-empty
                self.assertGreater(len(result), 0)
                # should be a list of enums
                for r in result:
                    self.assertIsInstance(r, zd.ZeroDayType)
                # should be unique
                self.assertEqual(len(result), len(set(result)))

    def test_type_from_history(self):
        for history in self.sg.histories:
            result = zd.type_from_history(history)
            if history in not_zero_day_histories:
                # should be empty
                self.assertEqual(len(result), 0)
            else:
                # should be non-empty
                self.assertGreaterEqual(len(result), 1)
                # should be a list of enums
                for r in result:
                    self.assertIsInstance(r, zd.ZeroDayType)
                # should be unique
                self.assertEqual(len(result), len(set(result)))


if __name__ == "__main__":
    unittest.main()
