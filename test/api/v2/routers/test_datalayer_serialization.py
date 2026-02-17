#!/usr/bin/env python
"""
Tests for data layer API serialization completeness.

Verifies that GET endpoints return all fields from stored objects,
not just base class fields.
"""
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

import pytest
from fastapi.testclient import TestClient

from vultron.api.main import app
from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_datalayer():
    """Reset data layer before each test."""
    dl = get_datalayer()
    dl.clear_all()
    yield
    dl.clear_all()


def test_get_vulnerability_case_includes_vulnerability_reports_field(client):
    """
    Test that GET /datalayer/{key} includes vulnerability_reports field.

    Regression test for bug where FastAPI's response_model filtering
    excluded subclass-specific fields.
    """
    # Create a report
    report = VulnerabilityReport(
        name="Test Report", content="Test vulnerability content"
    )

    # Create a case with the report
    case = VulnerabilityCase(
        name=f"Case for Report {report.as_id}",
        vulnerability_reports=[report],
        attributed_to="https://example.org/actor",
    )

    # Store both in data layer
    dl = get_datalayer()
    dl.create(report)
    dl.create(case)

    # Retrieve via API
    response = client.get(f"/api/v2/datalayer/{case.as_id}")

    assert response.status_code == 200
    data = response.json()

    # Verify response includes vulnerabilityReports field (camelCase)
    assert (
        "vulnerabilityReports" in data
    ), f"Response missing 'vulnerabilityReports' field. Keys: {list(data.keys())}"

    # Verify the field contains the report
    assert isinstance(data["vulnerabilityReports"], list)
    assert len(data["vulnerabilityReports"]) == 1
    assert data["vulnerabilityReports"][0]["id"] == report.as_id


def test_get_vulnerability_case_includes_all_fields(client):
    """
    Test that GET /datalayer/{key} includes all VulnerabilityCase fields.

    Ensures subclass-specific fields are not filtered by response_model.
    """
    # Create a case with various fields populated
    case = VulnerabilityCase(
        name="Comprehensive Test Case",
        attributed_to="https://example.org/actor",
        case_participants=[],  # Empty but should be included
        vulnerability_reports=[],  # Empty but should be included
        proposed_embargoes=[],  # Empty but should be included
        case_activity=[],  # Empty but should be included
    )

    # Store in data layer
    dl = get_datalayer()
    dl.create(case)

    # Retrieve via API
    response = client.get(f"/api/v2/datalayer/{case.as_id}")

    assert response.status_code == 200
    data = response.json()

    # Verify VulnerabilityCase-specific fields are present
    expected_fields = [
        "caseParticipants",
        "vulnerabilityReports",
        "caseStatus",
        "proposedEmbargoes",
        "caseActivity",
        "parentCases",
        "childCases",
        "siblingCases",
    ]

    for field in expected_fields:
        assert (
            field in data
        ), f"Response missing '{field}' field. Keys: {list(data.keys())}"


def test_get_vulnerability_report_includes_all_fields(client):
    """
    Test that GET /datalayer/{key} includes all VulnerabilityReport fields.

    Verifies the fix works for other subclasses too.
    """
    report = VulnerabilityReport(
        name="Test Report",
        content="Test vulnerability content",
        attributed_to="https://example.org/finder",
    )

    # Store in data layer
    dl = get_datalayer()
    dl.create(report)

    # Retrieve via API
    response = client.get(f"/api/v2/datalayer/{report.as_id}")

    assert response.status_code == 200
    data = response.json()

    # Verify VulnerabilityReport has content field (not in as_Base)
    assert (
        "content" in data
    ), f"Response missing 'content' field. Keys: {list(data.keys())}"
    assert data["content"] == "Test vulnerability content"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
