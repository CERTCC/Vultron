#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

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
