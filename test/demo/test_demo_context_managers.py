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

"""Tests for demo_step, demo_check, reset_demo_failures, and assert_demo_success.

The context managers accumulate errors rather than re-raising them.
assert_demo_success() raises DemoFailureError when failures have been recorded.
See specs/demo-ci.yaml DEMOCI-01-003, DEMOCI-01-004, DEMOCI-01-005.
"""

import logging

import pytest

import vultron.demo.utils as demo_utils
from vultron.demo.exchange.initialize_case_demo import demo_check, demo_step
from vultron.demo.utils import (
    assert_demo_success,
    reset_demo_failures,
)
from vultron.errors import DemoFailureError


@pytest.fixture(autouse=True)
def clear_failures():
    """Reset the failure accumulator before and after each test."""
    reset_demo_failures()
    yield
    reset_demo_failures()


class TestDemoStep:
    def test_step_logs_start_with_traffic_light(self, caplog):
        with caplog.at_level(logging.INFO):
            with demo_step("Step description"):
                pass
        assert any(
            "🚥" in r.message and "Step description" in r.message
            for r in caplog.records
        )

    def test_step_logs_success_on_clean_exit(self, caplog):
        with caplog.at_level(logging.INFO):
            with demo_step("Step description"):
                pass
        assert any(
            "🟢" in r.message and "Step description" in r.message
            for r in caplog.records
        )

    def test_step_logs_failure_on_exception(self, caplog):
        with caplog.at_level(logging.ERROR):
            with demo_step("Failing step"):
                raise ValueError("boom")
        assert any(
            "🔴" in r.message and "Failing step" in r.message
            for r in caplog.records
        )

    def test_step_does_not_reraise_exception(self):
        """demo_step accumulates the failure and does not re-raise (DEMOCI-01-003)."""
        with demo_step("Step that fails"):
            raise RuntimeError("expected")
        # execution reaches here — no re-raise

    def test_step_failure_added_to_accumulator(self):
        with demo_step("Failing step"):
            raise ValueError("oops")
        assert len(demo_utils._demo_failures) == 1
        assert "STEP FAILED" in demo_utils._demo_failures[0]
        assert "Failing step" in demo_utils._demo_failures[0]

    def test_step_start_is_info_level(self, caplog):
        with caplog.at_level(logging.INFO):
            with demo_step("Info step"):
                pass
        start_records = [r for r in caplog.records if "🚥" in r.message]
        assert start_records
        assert all(r.levelno == logging.INFO for r in start_records)

    def test_step_success_is_info_level(self, caplog):
        with caplog.at_level(logging.INFO):
            with demo_step("Info step"):
                pass
        success_records = [r for r in caplog.records if "🟢" in r.message]
        assert success_records
        assert all(r.levelno == logging.INFO for r in success_records)

    def test_step_failure_is_error_level(self, caplog):
        with caplog.at_level(logging.ERROR):
            with demo_step("Error step"):
                raise ValueError()
        failure_records = [r for r in caplog.records if "🔴" in r.message]
        assert failure_records
        assert all(r.levelno == logging.ERROR for r in failure_records)

    def test_no_failure_log_on_success(self, caplog):
        with caplog.at_level(logging.DEBUG):
            with demo_step("Clean step"):
                pass
        assert not any("🔴" in r.message for r in caplog.records)

    def test_no_success_log_on_failure(self, caplog):
        with caplog.at_level(logging.DEBUG):
            with demo_step("Bad step"):
                raise ValueError()
        assert not any("🟢" in r.message for r in caplog.records)

    def test_no_failure_added_on_success(self):
        with demo_step("Clean step"):
            pass
        assert demo_utils._demo_failures == []


class TestDemoCheck:
    def test_check_logs_start_with_clipboard(self, caplog):
        with caplog.at_level(logging.INFO):
            with demo_check("Check description"):
                pass
        assert any(
            "📋" in r.message and "Check description" in r.message
            for r in caplog.records
        )

    def test_check_logs_success_with_checkmark(self, caplog):
        with caplog.at_level(logging.INFO):
            with demo_check("Check description"):
                pass
        assert any(
            "✅" in r.message and "Check description" in r.message
            for r in caplog.records
        )

    def test_check_logs_failure_with_x(self, caplog):
        with caplog.at_level(logging.ERROR):
            with demo_check("Failing check"):
                raise AssertionError("not found")
        assert any(
            "❌" in r.message and "Failing check" in r.message
            for r in caplog.records
        )

    def test_check_does_not_reraise_exception(self):
        """demo_check accumulates the failure and does not re-raise (DEMOCI-01-003)."""
        with demo_check("Check that fails"):
            raise AssertionError("missing")
        # execution reaches here — no re-raise

    def test_check_failure_added_to_accumulator(self):
        with demo_check("Failing check"):
            raise AssertionError("bad state")
        assert len(demo_utils._demo_failures) == 1
        assert "CHECK FAILED" in demo_utils._demo_failures[0]
        assert "Failing check" in demo_utils._demo_failures[0]

    def test_check_start_is_info_level(self, caplog):
        with caplog.at_level(logging.INFO):
            with demo_check("Info check"):
                pass
        start_records = [r for r in caplog.records if "📋" in r.message]
        assert start_records
        assert all(r.levelno == logging.INFO for r in start_records)

    def test_check_success_is_info_level(self, caplog):
        with caplog.at_level(logging.INFO):
            with demo_check("Info check"):
                pass
        success_records = [r for r in caplog.records if "✅" in r.message]
        assert success_records
        assert all(r.levelno == logging.INFO for r in success_records)

    def test_check_failure_is_error_level(self, caplog):
        with caplog.at_level(logging.ERROR):
            with demo_check("Error check"):
                raise AssertionError()
        failure_records = [r for r in caplog.records if "❌" in r.message]
        assert failure_records
        assert all(r.levelno == logging.ERROR for r in failure_records)

    def test_no_failure_log_on_success(self, caplog):
        with caplog.at_level(logging.DEBUG):
            with demo_check("Clean check"):
                pass
        assert not any("❌" in r.message for r in caplog.records)

    def test_no_success_log_on_failure(self, caplog):
        with caplog.at_level(logging.DEBUG):
            with demo_check("Bad check"):
                raise AssertionError()
        assert not any("✅" in r.message for r in caplog.records)

    def test_no_failure_added_on_success(self):
        with demo_check("Clean check"):
            pass
        assert demo_utils._demo_failures == []


class TestDemoAccumulator:
    def test_reset_clears_failures(self):
        demo_utils._demo_failures.append("prior failure")
        reset_demo_failures()
        assert demo_utils._demo_failures == []

    def test_assert_success_raises_when_failures_present(self):
        demo_utils._demo_failures.append("STEP FAILED: foo — ValueError()")
        with pytest.raises(DemoFailureError):
            assert_demo_success()

    def test_assert_success_does_not_raise_when_no_failures(self):
        assert demo_utils._demo_failures == []
        assert_demo_success()  # should not raise

    def test_demo_failure_error_carries_failures_list(self):
        msg = "STEP FAILED: bar — RuntimeError(boom)"
        demo_utils._demo_failures.append(msg)
        with pytest.raises(DemoFailureError) as exc_info:
            assert_demo_success()
        assert msg in exc_info.value.failures

    def test_multiple_failures_accumulated(self):
        with demo_step("Step 1"):
            raise ValueError("v1")
        with demo_check("Check 1"):
            raise AssertionError("a1")
        with demo_step("Step 2"):
            raise RuntimeError("r1")
        assert len(demo_utils._demo_failures) == 3

    def test_assert_success_message_includes_count(self):
        demo_utils._demo_failures.extend(["f1", "f2"])
        with pytest.raises(DemoFailureError, match="2 demo failure"):
            assert_demo_success()

    def test_is_subclass_of_vultron_error(self):
        from vultron.errors import VultronError

        assert issubclass(DemoFailureError, VultronError)
