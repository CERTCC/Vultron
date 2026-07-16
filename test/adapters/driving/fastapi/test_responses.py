#!/usr/bin/env python
"""
Unit tests for AS2JSONResponse.

HTTP-09-002: Route handlers returning AS2 objects MUST use AS2JSONResponse.
HTTP-09-003: Correct Content-Type and serialization behaviour.
HTTP-08-001: Subclass fields must NOT be stripped (regression test).
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

import json

from vultron.adapters.driving.fastapi.responses import (
    AS2_CONTENT_TYPE,
    AS2JSONResponse,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)


def test_content_type_is_as2():
    """AS2JSONResponse must set Content-Type: application/activity+json."""
    report = VulnerabilityReport(name="test")
    response = AS2JSONResponse(report)
    assert response.media_type == AS2_CONTENT_TYPE
    assert AS2_CONTENT_TYPE in response.headers["content-type"]


def test_camelcase_keys():
    """AS2JSONResponse must serialize with by_alias=True (camelCase keys)."""
    case = VulnerabilityCase(
        name="Test Case",
        attributed_to="https://example.org/actor",
        vulnerability_reports=[],
    )
    response = AS2JSONResponse(case)
    body = json.loads(bytes(response.body))

    # vulnerability_reports → vulnerabilityReports (camelCase)
    assert (
        "vulnerabilityReports" in body
    ), f"Expected 'vulnerabilityReports' in body keys: {list(body.keys())}"
    # snake_case key must NOT appear
    assert "vulnerability_reports" not in body


def test_subclass_fields_not_stripped():
    """Subclass-specific fields must be present — HTTP-08-001 regression test.

    FastAPI's response_model filtering strips fields not declared on the base
    class. AS2JSONResponse bypasses that filtering entirely.
    """
    report = VulnerabilityReport(
        name="Test Report",
        content="Test vulnerability content",
        attributed_to="https://example.org/finder",
    )
    case = VulnerabilityCase(
        name="Test Case",
        attributed_to="https://example.org/actor",
        vulnerability_reports=[report],
        case_participants=[],
        proposed_embargoes=[],
        case_activity=[],
    )
    response = AS2JSONResponse(case)
    body = json.loads(bytes(response.body))

    case_specific_fields = [
        "vulnerabilityReports",
        "caseParticipants",
        "proposedEmbargoes",
        "caseActivity",
    ]
    for field in case_specific_fields:
        assert field in body, (
            f"Subclass field '{field}' missing from response. "
            f"Keys present: {list(body.keys())}"
        )


def test_exclude_none_true():
    """None-valued fields must be omitted from the serialized body."""
    report = VulnerabilityReport(name="Minimal Report")
    response = AS2JSONResponse(report)
    body = json.loads(bytes(response.body))

    # Fields that are None should be absent, not null
    for key, value in body.items():
        assert (
            value is not None
        ), f"Field '{key}' is null — exclude_none=True should have dropped it"


def test_non_as2_content_passthrough():
    """Non-as_Base content is passed through unchanged (dict/list fallback)."""
    data = {"key": "value", "number": 42}
    response = AS2JSONResponse(data)
    body = json.loads(bytes(response.body))

    assert body == data
    assert response.media_type == AS2_CONTENT_TYPE


def test_status_code_default():
    """Default status code is 200."""
    report = VulnerabilityReport(name="Test")
    response = AS2JSONResponse(report)
    assert response.status_code == 200


def test_status_code_override():
    """Custom status codes are forwarded correctly."""
    report = VulnerabilityReport(name="Created")
    response = AS2JSONResponse(report, status_code=201)
    assert response.status_code == 201
