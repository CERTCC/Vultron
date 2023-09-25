#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

import unittest
from enum import Enum

import vultron.cvd_states.patterns.info as info
from vultron.cvd_states.hypercube import CVDmodel


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
