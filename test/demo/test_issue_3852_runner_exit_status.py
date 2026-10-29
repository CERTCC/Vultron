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

"""Regression tests for ISSUE-3852.

``run_exchange_demos`` must raise ``DemoFailureError`` once every selected demo
has run when any of them recorded a failure, so an exchange demo's ``main()``
— and the ``vultron-demo`` sub-command and ``all`` built on it — exits
non-zero (DEMOCI-01-001, DEMOCI-01-003).  The receive-report Demo 1 case
lookup is a causal precondition: a missing case is one gated failure, and the
introduction check that needs the case does not run (DEMOCI-01-007).
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from vultron.demo.exchange import receive_report_demo
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.utils import (
    assert_demo_success,
    demo_gate,
    demo_step,
    reset_demo_failures,
)
from vultron.errors import DemoFailureError


@contextmanager
def _fake_demo_environment(client):
    """Yield stub actors without requiring a live server."""
    yield MagicMock(), MagicMock(), MagicMock()


@pytest.fixture(autouse=True)
def _reset_failures():
    reset_demo_failures()
    yield
    reset_demo_failures()


@pytest.fixture
def fake_environment():
    with patch(
        "vultron.demo.helpers.runner.demo_environment",
        _fake_demo_environment,
    ):
        yield


def _failing_step(client, reporter, vendor, coordinator):
    with demo_step("injected step"):
        raise ValueError("step went wrong")


def _timing_out_gate(client, reporter, vendor, coordinator):
    with demo_gate("injected precondition"):
        raise TimeoutError("timed out waiting")


def _passing(client, reporter, vendor, coordinator):
    with demo_step("fine step"):
        pass


def _hard_failure(client, reporter, vendor, coordinator):
    raise RuntimeError("hard failure")


class TestRunnerRaisesOnFailure:
    @pytest.mark.usefixtures("fake_environment")
    def test_run_exchange_demos_raises_demo_failure_error_when_a_step_fails(
        self,
    ) -> None:
        with pytest.raises(DemoFailureError) as exc_info:
            run_exchange_demos(
                [("step demo", _failing_step)], skip_health_check=True
            )
        assert len(exc_info.value.failures) == 1
        assert "step demo" in exc_info.value.failures[0]
        assert "step went wrong" in exc_info.value.failures[0]

    @pytest.mark.usefixtures("fake_environment")
    def test_run_exchange_demos_raises_when_a_gate_times_out(self) -> None:
        with pytest.raises(DemoFailureError) as exc_info:
            run_exchange_demos(
                [("gate demo", _timing_out_gate)], skip_health_check=True
            )
        assert "timed out waiting" in str(exc_info.value)

    @pytest.mark.usefixtures("fake_environment")
    def test_run_exchange_demos_raises_on_a_hard_exception(self) -> None:
        with pytest.raises(DemoFailureError) as exc_info:
            run_exchange_demos(
                [("hard demo", _hard_failure)], skip_health_check=True
            )
        assert "hard failure" in exc_info.value.failures[0]

    @pytest.mark.usefixtures("fake_environment")
    def test_run_exchange_demos_runs_every_demo_before_raising(self) -> None:
        calls: list[str] = []

        def _recording(client, reporter, vendor, coordinator):
            calls.append("ran")

        with pytest.raises(DemoFailureError) as exc_info:
            run_exchange_demos(
                [
                    ("first", _failing_step),
                    ("second", _recording),
                    ("third", _timing_out_gate),
                ],
                skip_health_check=True,
            )
        assert calls == ["ran"]
        failures = exc_info.value.failures
        assert len(failures) == 2
        assert failures[0].startswith("first")
        assert failures[1].startswith("third")

    @pytest.mark.usefixtures("fake_environment")
    def test_run_exchange_demos_returns_when_all_demos_pass(self) -> None:
        run_exchange_demos(
            [("one", _passing), ("two", _passing)], skip_health_check=True
        )


class TestReceiveReportCaseLookupIsGated:
    """AC-3: Demo 1 Step 3 records a missing case once, through ``demo_gate``."""

    def test_missing_case_is_one_gated_failure_and_skips_introduction_check(
        self,
    ) -> None:
        report = MagicMock()
        offer = MagicMock()
        verify_intro = MagicMock()
        with (
            patch.object(
                receive_report_demo,
                "reporter_submits_report",
                return_value=(report, offer),
            ),
            patch.object(receive_report_demo, "get_offer_from_datalayer"),
            patch.object(receive_report_demo, "rm_validate_report_activity"),
            patch.object(receive_report_demo, "post_to_inbox_and_wait"),
            patch.object(
                receive_report_demo, "verify_received_activity_stored"
            ),
            patch.object(
                receive_report_demo, "find_case_by_report", return_value=None
            ),
            patch.object(
                receive_report_demo,
                "verify_reporter_trusts_introduction",
                verify_intro,
            ),
        ):
            receive_report_demo.demo_validate_report(
                MagicMock(), MagicMock(), MagicMock()
            )

        verify_intro.assert_not_called()
        with pytest.raises(DemoFailureError) as exc_info:
            assert_demo_success()
        failures = exc_info.value.failures
        assert len(failures) == 1, failures
        assert "Case created for report" in failures[0]
