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
#
#  See LICENSE for details

import unittest

from vultron.bt.embargo_management.states import EM


class TestEmbargoStates(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_embargo_states(self):
        self.assertIs(EM.NO_EMBARGO, EM.N)
        self.assertIs(EM.PROPOSED, EM.P)
        self.assertIs(EM.ACTIVE, EM.A)
        self.assertIs(EM.REVISE, EM.R)
        self.assertIs(EM.EXITED, EM.X)

    def test_embargo_state_names(self):
        self.assertEqual("EMBARGO_MANAGEMENT_NONE", EM.N.name)
        self.assertEqual("EMBARGO_MANAGEMENT_PROPOSED", EM.P.name)
        self.assertEqual("EMBARGO_MANAGEMENT_ACTIVE", EM.A.name)
        self.assertEqual("EMBARGO_MANAGEMENT_REVISE", EM.R.name)
        self.assertEqual("EMBARGO_MANAGEMENT_EXITED", EM.X.name)


if __name__ == "__main__":
    unittest.main()
