#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

import unittest

import vultron.cvd_states.enums.vep
from vultron.cvd_states.hypercube import CVDmodel
from vultron.cvd_states.patterns import vep


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.model = CVDmodel()

    def tearDown(self):
        pass

    def test_vep(self):
        for state in self.model.states:
            result = vep.vep(state)
            # result should always be a list of non-zero length of strings of non-zero length
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            for item in result:
                self.assertIsInstance(item, vultron.cvd_states.enums.vep.VEP)


if __name__ == "__main__":
    unittest.main()
