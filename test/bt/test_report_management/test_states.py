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
from typing import Sequence

from vultron.bt.report_management.states import (
    RM,
    RM_ACTIVE,
    RM_CLOSABLE,
    RM_UNCLOSED,
)


class MyTestCase(unittest.TestCase):
    def test_rm_enum(self):
        self.assertGreater(len(RM), 0)

        for (
            medname
        ) in "START RECEIVED INVALID VALID DEFERRED ACCEPTED CLOSED".split():
            shortname = medname[0]
            self.assertTrue(
                hasattr(RM, shortname), f"RM does not have {shortname}"
            )
            self.assertEqual(
                medname,
                getattr(RM, shortname).value,
                f"RM.{shortname} does not have value {medname}",
            )

            self.assertTrue(
                hasattr(RM, medname), f"RM does not have {medname}"
            )
            self.assertEqual(
                medname,
                getattr(RM, medname).value,
                f"RM.{medname} does not have value {medname}",
            )

            longname = f"REPORT_MANAGEMENT_{medname}"
            self.assertTrue(
                hasattr(RM, longname), f"RM does not have {longname}"
            )
            self.assertEqual(
                medname,
                getattr(RM, longname).value,
                f"RM.{longname} does not have value {medname}",
            )

    def _test_convenience_aliases(self, alias, values: Sequence[RM]):
        for s in RM:
            if s in values:
                self.assertIn(s, alias)
            else:
                self.assertNotIn(s, alias)

    def test_closable(self):
        self._test_convenience_aliases(RM_CLOSABLE, (RM.I, RM.D, RM.A))

    def test_unclosed(self):
        self._test_convenience_aliases(
            RM_UNCLOSED, (RM.S, RM.R, RM.I, RM.V, RM.D, RM.A)
        )

    def test_active(self):
        self._test_convenience_aliases(RM_ACTIVE, (RM.R, RM.V, RM.A))


if __name__ == "__main__":
    unittest.main()
