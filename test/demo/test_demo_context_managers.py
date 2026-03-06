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

"""Tests for demo_step and demo_check context managers in initialize_case_demo."""

import logging

import pytest

from vultron.demo.initialize_case_demo import demo_check, demo_step


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
            with pytest.raises(ValueError):
                with demo_step("Failing step"):
                    raise ValueError("boom")
        assert any(
            "🔴" in r.message and "Failing step" in r.message
            for r in caplog.records
        )

    def test_step_reraises_exception(self):
        with pytest.raises(RuntimeError, match="expected"):
            with demo_step("Step that fails"):
                raise RuntimeError("expected")

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
            with pytest.raises(ValueError):
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
            with pytest.raises(ValueError):
                with demo_step("Bad step"):
                    raise ValueError()
        assert not any("🟢" in r.message for r in caplog.records)


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
            with pytest.raises(AssertionError):
                with demo_check("Failing check"):
                    raise AssertionError("not found")
        assert any(
            "❌" in r.message and "Failing check" in r.message
            for r in caplog.records
        )

    def test_check_reraises_exception(self):
        with pytest.raises(AssertionError, match="missing"):
            with demo_check("Check that fails"):
                raise AssertionError("missing")

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
            with pytest.raises(AssertionError):
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
            with pytest.raises(AssertionError):
                with demo_check("Bad check"):
                    raise AssertionError()
        assert not any("✅" in r.message for r in caplog.records)
