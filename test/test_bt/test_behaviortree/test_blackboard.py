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

from vultron.bt.base.blackboard import BlackBoard


class TestBlackBoard(unittest.TestCase):
    def test_bb_has_dict_semantics(self):
        bb = BlackBoard()

        self.assertTrue(hasattr(bb, "__getitem__"))
        self.assertTrue(hasattr(bb, "__setitem__"))
        self.assertTrue(hasattr(bb, "__delitem__"))
        self.assertTrue(hasattr(bb, "__contains__"))
        self.assertTrue(hasattr(bb, "get"))

        self.assertNotIn("foo", bb)
        self.assertEqual(None, bb.get("foo"))

        bb["foo"] = "bar"

        self.assertIn("foo", bb)
        self.assertEqual("bar", bb["foo"])
        self.assertEqual("bar", bb.get("foo"))

        del bb["foo"]
        self.assertNotIn("foo", bb)


if __name__ == "__main__":
    unittest.main()
