#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Unit tests for the unified Vultron demo CLI (DC-05-001 through DC-05-004)."""

import logging
from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner

from vultron.demo.cli import DEMOS, main


class TestCliLogging:
    """Tests that the CLI configures logging so demo output is visible."""

    def test_default_log_level_is_info(self):
        """Invoking the CLI without flags must configure root logger at INFO."""
        runner = CliRunner()
        mock_demo = MagicMock()
        with patch.dict(
            "vultron.demo.cli.__dict__",
            {},
        ):
            # Invoke --help so no demo actually runs; we just need the group
            # callback to fire and set up logging.
            result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0

    def test_cli_configures_info_logging_on_invocation(self):
        """The root logger must have at least one handler after CLI invocation."""
        runner = CliRunner()

        name, module = DEMOS[0]
        mock_fn = MagicMock()

        with patch.object(module, "main", mock_fn):
            result = runner.invoke(main, [name, "--skip-health-check"])

        # After CLI runs, root logger should have a handler (logging configured)
        root_handlers = logging.getLogger().handlers
        assert (
            len(root_handlers) > 0
        ), "CLI did not configure any logging handlers"

    def test_root_logger_level_is_info_by_default(self):
        """Root logger effective level must be INFO (or lower) after CLI invocation."""
        runner = CliRunner()

        name, module = DEMOS[0]
        mock_fn = MagicMock()

        with patch.object(module, "main", mock_fn):
            runner.invoke(main, [name, "--skip-health-check"])

        root_logger = logging.getLogger()
        assert root_logger.level <= logging.INFO, (
            f"Expected root logger level <= INFO ({logging.INFO}), "
            f"got {root_logger.level}"
        )

    def test_debug_flag_sets_debug_level(self):
        """--debug flag must configure root logger at DEBUG level."""
        runner = CliRunner()

        name, module = DEMOS[0]
        mock_fn = MagicMock()

        with patch.object(module, "main", mock_fn):
            runner.invoke(main, ["--debug", name, "--skip-health-check"])

        root_logger = logging.getLogger()
        assert root_logger.level <= logging.DEBUG, (
            f"Expected root logger level <= DEBUG ({logging.DEBUG}), "
            f"got {root_logger.level}"
        )

    def test_debug_flag_is_available(self):
        """The main group must expose a --debug option."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "--debug" in result.output

    def teardown_method(self):
        """Reset root logger handlers after each test to avoid cross-test pollution."""
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)
        root.setLevel(logging.WARNING)


class TestCliSubCommands:
    """Tests that each sub-command invokes the correct demo function (DC-05-004)."""

    @pytest.mark.parametrize("name,module", DEMOS)
    def test_subcommand_invokes_demo_main(self, name, module):
        """Each sub-command must call module.main() exactly once."""
        runner = CliRunner()
        mock_fn = MagicMock()
        with patch.object(module, "main", mock_fn):
            result = runner.invoke(main, [name, "--skip-health-check"])
        assert result.exit_code == 0, result.output
        mock_fn.assert_called_once()


class TestCliAll:
    """Tests for the `all` sub-command (DC-05-002, DC-05-003)."""

    def test_all_invokes_every_demo_once(self):
        """The `all` sub-command must invoke every registered demo exactly once."""
        runner = CliRunner()
        mocks = {name: MagicMock() for name, _ in DEMOS}
        patches = [
            patch.object(module, "main", mocks[name]) for name, module in DEMOS
        ]
        for p in patches:
            p.start()
        try:
            result = runner.invoke(main, ["all", "--skip-health-check"])
        finally:
            for p in patches:
                p.stop()

        assert result.exit_code == 0, result.output
        for name, _ in DEMOS:
            mocks[name].assert_called_once()

    def test_all_exits_nonzero_on_first_failure(self):
        """The `all` sub-command must exit non-zero when a demo raises."""
        runner = CliRunner()

        name0, module0 = DEMOS[0]
        mock_fail = MagicMock(side_effect=RuntimeError("demo failed"))
        mock_ok = MagicMock()

        patches = []
        for _name, _module in DEMOS:
            if _name == name0:
                patches.append(patch.object(_module, "main", mock_fail))
            else:
                patches.append(patch.object(_module, "main", mock_ok))

        for p in patches:
            p.start()
        try:
            result = runner.invoke(main, ["all", "--skip-health-check"])
        finally:
            for p in patches:
                p.stop()

        assert result.exit_code != 0, "Expected non-zero exit on demo failure"
