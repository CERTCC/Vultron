#!/usr/bin/env python

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

"""
Tests for report validation policy implementations.

This module tests the ValidationPolicy interface and AlwaysAcceptPolicy
implementation, verifying policy decision logic and logging behavior.
"""

import logging
from unittest.mock import MagicMock

import pytest

from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.behaviors.report.policy import (
    AlwaysAcceptPolicy,
    ValidationPolicy,
)


class TestValidationPolicy:
    """Test ValidationPolicy abstract base class."""

    def test_abstract_is_credible_raises(self):
        """ValidationPolicy.is_credible() raises NotImplementedError."""
        policy = ValidationPolicy()
        report = VulnerabilityReport(
            as_id="https://example.org/reports/test-001",
            name="TEST-001",
            content="Test report",
        )

        with pytest.raises(NotImplementedError, match="is_credible"):
            policy.is_credible(report)

    def test_abstract_is_valid_raises(self):
        """ValidationPolicy.is_valid() raises NotImplementedError."""
        policy = ValidationPolicy()
        report = VulnerabilityReport(
            as_id="https://example.org/reports/test-001",
            name="TEST-001",
            content="Test report",
        )

        with pytest.raises(NotImplementedError, match="is_valid"):
            policy.is_valid(report)

    def test_subclass_implementation_pattern(self):
        """Subclass can implement both methods successfully."""

        class CustomPolicy(ValidationPolicy):
            def is_credible(self, report):
                return len(report.name) > 5

            def is_valid(self, report):
                return "vulnerability" in report.content.lower()

        policy = CustomPolicy()

        # Short name → not credible
        report1 = VulnerabilityReport(
            as_id="https://example.org/reports/r1",
            name="CVE-1",
            content="Vulnerability found",
        )
        assert not policy.is_credible(report1)
        assert policy.is_valid(report1)

        # Long name → credible
        report2 = VulnerabilityReport(
            as_id="https://example.org/reports/r2",
            name="CVE-2024-12345",
            content="Vulnerability found",
        )
        assert policy.is_credible(report2)
        assert policy.is_valid(report2)

        # No keyword → invalid
        report3 = VulnerabilityReport(
            as_id="https://example.org/reports/r3",
            name="CVE-2024-12345",
            content="Bug found",
        )
        assert policy.is_credible(report3)
        assert not policy.is_valid(report3)


class TestAlwaysAcceptPolicy:
    """Test AlwaysAcceptPolicy implementation."""

    def test_is_credible_returns_true(self):
        """AlwaysAcceptPolicy.is_credible() always returns True."""
        policy = AlwaysAcceptPolicy()
        report = VulnerabilityReport(
            as_id="https://example.org/reports/test-001",
            name="TEST-001",
            content="Test report",
        )

        assert policy.is_credible(report) is True

    def test_is_valid_returns_true(self):
        """AlwaysAcceptPolicy.is_valid() always returns True."""
        policy = AlwaysAcceptPolicy()
        report = VulnerabilityReport(
            as_id="https://example.org/reports/test-001",
            name="TEST-001",
            content="Test report",
        )

        assert policy.is_valid(report) is True

    def test_is_credible_logs_at_info_level(self, caplog):
        """AlwaysAcceptPolicy.is_credible() logs acceptance at INFO level."""
        policy = AlwaysAcceptPolicy()
        report = VulnerabilityReport(
            as_id="https://example.org/reports/test-001",
            name="TEST-001",
            content="Test report",
        )

        with caplog.at_level(logging.INFO):
            result = policy.is_credible(report)

        assert result is True
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        assert "credible" in caplog.records[0].message
        assert "AlwaysAcceptPolicy" in caplog.records[0].message
        assert report.as_id in caplog.records[0].message

    def test_is_valid_logs_at_info_level(self, caplog):
        """AlwaysAcceptPolicy.is_valid() logs acceptance at INFO level."""
        policy = AlwaysAcceptPolicy()
        report = VulnerabilityReport(
            as_id="https://example.org/reports/test-001",
            name="TEST-001",
            content="Test report",
        )

        with caplog.at_level(logging.INFO):
            result = policy.is_valid(report)

        assert result is True
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        assert "valid" in caplog.records[0].message
        assert "AlwaysAcceptPolicy" in caplog.records[0].message
        assert report.as_id in caplog.records[0].message

    def test_multiple_reports_always_accepted(self):
        """AlwaysAcceptPolicy accepts all reports regardless of content."""
        policy = AlwaysAcceptPolicy()

        reports = [
            VulnerabilityReport(
                as_id="https://example.org/reports/r1",
                name="CVE-2024-001",
                content="Buffer overflow",
            ),
            VulnerabilityReport(
                as_id="https://example.org/reports/r2",
                name="",  # Empty name
                content="",  # Empty content
            ),
            VulnerabilityReport(
                as_id="https://example.org/reports/r3",
                name="X" * 1000,  # Very long name
                content="Y" * 10000,  # Very long content
            ),
        ]

        for report in reports:
            assert (
                policy.is_credible(report) is True
            ), f"Failed for {report.as_id}"
            assert (
                policy.is_valid(report) is True
            ), f"Failed for {report.as_id}"

    def test_policy_reusable_across_reports(self):
        """Single AlwaysAcceptPolicy instance can evaluate multiple reports."""
        policy = AlwaysAcceptPolicy()

        report1 = VulnerabilityReport(
            as_id="https://example.org/reports/r1",
            name="Report 1",
            content="Content 1",
        )
        report2 = VulnerabilityReport(
            as_id="https://example.org/reports/r2",
            name="Report 2",
            content="Content 2",
        )

        # First report
        assert policy.is_credible(report1) is True
        assert policy.is_valid(report1) is True

        # Second report (same policy instance)
        assert policy.is_credible(report2) is True
        assert policy.is_valid(report2) is True

    def test_policy_does_not_mutate_report(self):
        """AlwaysAcceptPolicy does not modify report object."""
        policy = AlwaysAcceptPolicy()
        report = VulnerabilityReport(
            as_id="https://example.org/reports/test-001",
            name="TEST-001",
            content="Test report",
        )

        # Store original values
        original_id = report.as_id
        original_name = report.name
        original_content = report.content

        # Evaluate
        policy.is_credible(report)
        policy.is_valid(report)

        # Verify no mutation
        assert report.as_id == original_id
        assert report.name == original_name
        assert report.content == original_content

    def test_inherits_from_validation_policy(self):
        """AlwaysAcceptPolicy is a ValidationPolicy subclass."""
        policy = AlwaysAcceptPolicy()
        assert isinstance(policy, ValidationPolicy)

    def test_log_messages_include_report_id(self, caplog):
        """Policy log messages include report ID for traceability."""
        policy = AlwaysAcceptPolicy()
        report_id = "https://example.org/reports/traced-report-123"
        report = VulnerabilityReport(
            as_id=report_id,
            name="TRACED-123",
            content="Traceable report",
        )

        with caplog.at_level(logging.INFO):
            policy.is_credible(report)
            policy.is_valid(report)

        # Both log messages should contain the report ID
        assert len(caplog.records) == 2
        assert all(report_id in record.message for record in caplog.records)
