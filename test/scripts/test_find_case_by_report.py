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
"""Tests for find_case_by_report function."""

from unittest.mock import Mock

from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.scripts.receive_report_demo import find_case_by_report


def test_find_case_by_report_with_vulnerability_reports_field():
    """
    Test that find_case_by_report correctly finds a case by checking the
    vulnerability_reports field (not content field).

    This test reproduces the bug where find_case_by_report was looking at
    case_obj.content instead of case_obj.vulnerability_reports, causing
    cases to not be found even though they existed.
    """
    # Create a test report
    report = VulnerabilityReport(
        name="Test Vulnerability Report",
        content="This is a test vulnerability report content.",
    )

    # Create a case that references this report via vulnerability_reports field
    case = VulnerabilityCase(
        name=f"Case for Report {report.as_id}",
        vulnerability_reports=[
            report.as_id
        ],  # Field name is vulnerability_reports
    )

    # Mock the DataLayerClient
    mock_client = Mock()
    # When get is called for VulnerabilityCases, return a list with our case dict
    mock_client.get.return_value = [case.model_dump(by_alias=True)]

    # Now try to find the case by report ID
    found_case = find_case_by_report(mock_client, report.as_id)

    # This should find the case
    assert found_case is not None, "Case should be found by report ID"
    assert (
        found_case.as_id == case.as_id
    ), "Found case should match created case"
    assert (
        report.as_id in found_case.vulnerability_reports
    ), "Case should contain report ID in vulnerability_reports field"
