#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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

"""Regression tests for ISSUE-2360.

``run_exchange_demos`` must attach accumulated soft failures as notes on any
in-flight hard exception, mirroring the pattern in
``scenario_harness._note_accumulated_failures``.
"""

import logging
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.utils import demo_check, reset_demo_failures


@contextmanager
def _fake_demo_environment(client):
    """Yield stub actors without requiring a live server."""
    yield MagicMock(), MagicMock(), MagicMock()


@pytest.fixture(autouse=True)
def _reset_failures():
    reset_demo_failures()
    yield
    reset_demo_failures()


class TestRunnerSoftFailuresOnException:
    def test_soft_failures_attached_as_notes_when_hard_exception_occurs(
        self, caplog
    ) -> None:
        """Soft failures accumulated before a hard exception ride along as notes."""
        soft_msg = "a soft precondition"

        def demo_fn(client, finder, vendor, coordinator):
            with demo_check(soft_msg):
                raise AssertionError("precondition not met")
            raise RuntimeError("hard failure")

        with patch(
            "vultron.demo.helpers.runner.demo_environment",
            _fake_demo_environment,
        ):
            with caplog.at_level(logging.ERROR):
                run_exchange_demos(
                    [("test_demo", demo_fn)], skip_health_check=True
                )

        hard_exc_records = [
            r
            for r in caplog.records
            if r.exc_info and isinstance(r.exc_info[1], RuntimeError)
        ]
        assert hard_exc_records, "Expected an ERROR record with a RuntimeError"

        exc_value = hard_exc_records[0].exc_info[1]
        notes = getattr(exc_value, "__notes__", [])
        assert any(
            soft_msg in note for note in notes
        ), f"Expected '{soft_msg}' in exception notes {notes!r}"

    def test_no_notes_when_no_soft_failures_occurred(self, caplog) -> None:
        """A hard exception without prior soft failures has no extra notes."""

        def demo_fn(client, finder, vendor, coordinator):
            raise RuntimeError("hard failure only")

        with patch(
            "vultron.demo.helpers.runner.demo_environment",
            _fake_demo_environment,
        ):
            with caplog.at_level(logging.ERROR):
                run_exchange_demos(
                    [("test_demo", demo_fn)], skip_health_check=True
                )

        hard_exc_records = [
            r
            for r in caplog.records
            if r.exc_info and isinstance(r.exc_info[1], RuntimeError)
        ]
        assert hard_exc_records
        exc_value = hard_exc_records[0].exc_info[1]
        notes = getattr(exc_value, "__notes__", [])
        assert (
            not notes
        ), f"Expected no notes on a clean hard exception, got {notes!r}"

    def test_second_demo_runs_after_first_fails(self) -> None:
        """A failed demo does not prevent subsequent demos from running."""
        calls: list[str] = []

        def demo_fails(client, finder, vendor, coordinator):
            with demo_check("soft check in failing demo"):
                raise AssertionError("soft")
            raise RuntimeError("hard failure")

        def demo_succeeds(client, finder, vendor, coordinator):
            calls.append("ran")

        with patch(
            "vultron.demo.helpers.runner.demo_environment",
            _fake_demo_environment,
        ):
            run_exchange_demos(
                [("demo1", demo_fails), ("demo2", demo_succeeds)],
                skip_health_check=True,
            )

        assert "ran" in calls, "Second demo must run even after first fails"
