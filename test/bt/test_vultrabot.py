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

import logging
import unittest
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from vultron.bt import behaviors
from vultron.bt.base.demo import cvd as vultrabot


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
        always_present = [
            "q_rm",
            "q_em",
            "q_cs",
            "RS",
            "START",
            "NONE",
            "vfdpxa",
            "FINDER_REPORTER_VENDOR_DEPLOYER_COORDINATOR",
        ]
        for item in always_present:
            with self.subTest(item=item):
                self.assertIn(item, output)

        # CLOSED only appears when at least one simulation reached closure
        if any_closed:
            with self.subTest(item="CLOSED"):
                self.assertIn("CLOSED", output)


def test_reset_statelog_empties_the_list_every_importer_holds():
    """``reset_statelog`` clears in place, so ``cvd``'s import stays live (#3985)."""
    held = behaviors.STATELOG
    held.append({"q_rm": "sentinel"})

    behaviors.reset_statelog()

    assert behaviors.STATELOG is held
    assert vultrabot.STATELOG is held
    assert held == []


def test_setup_logger_routes_module_records_to_the_root_handler():
    """The module logger is left alone; its records reach the root handler."""
    root = logging.getLogger()
    saved_level, saved_handlers = root.level, list(root.handlers)
    module_logger = vultrabot.logger
    try:
        vultrabot._setup_logger(SimpleNamespace(log_level=logging.INFO))
        assert vultrabot.logger is module_logger
        assert module_logger.name == vultrabot.__name__
        assert root.level == logging.INFO
        assert module_logger.getEffectiveLevel() == logging.INFO
        added = [h for h in root.handlers if h not in saved_handlers]
        assert len(added) == 1
        assert isinstance(added[0], logging.StreamHandler)
    finally:
        for handler in [h for h in root.handlers if h not in saved_handlers]:
            root.removeHandler(handler)
        root.setLevel(saved_level)


if __name__ == "__main__":
    unittest.main()
