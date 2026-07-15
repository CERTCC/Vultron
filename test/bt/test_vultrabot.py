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
from io import StringIO
from unittest.mock import patch

from vultron.demo import vultrabot


class MyTestCase(unittest.TestCase):
    # capture stdout
    @patch("sys.stdout", new_callable=StringIO)
    def test_main(self, stdout):
        any_closed = False
        for _ in range(10):
            # capture the output
            closed = vultrabot._run_simulation()
            any_closed = any_closed or closed
            vultrabot._print_sim_result()

        # test the output
        self.assertIsNotNone(stdout)
        output = stdout.getvalue()

        # things that are consistently in the output
        always_present = "q_rm q_em q_cs RS START NONE vfdpxa FINDER_REPORTER_VENDOR_DEPLOYER_COORDINATOR".split()
        for item in always_present:
            with self.subTest(item=item):
                self.assertIn(item, output)

        # CLOSED only appears when at least one simulation reached closure
        if any_closed:
            with self.subTest(item="CLOSED"):
                self.assertIn("CLOSED", output)


if __name__ == "__main__":
    unittest.main()
