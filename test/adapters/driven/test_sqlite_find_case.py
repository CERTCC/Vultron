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

"""Tests for SqliteDataLayer case-lookup helpers.

Covers: find_case_by_short_id (HTTP URL and URN IDs, ambiguity guard) and
find_case_by_report_id (via vulnerability_reports list and ReportCaseLink).
Fixtures (dl) come from conftest.
"""

# ---------------------------------------------------------------------------
# find_case_by_short_id tests
# ---------------------------------------------------------------------------


def test_find_case_by_short_id_with_http_url_case_id(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )

    case = VulnerabilityCase(id_="https://example.org/api/v2/cases/demo-123")
    dl.save(case)

    result = dl.find_case_by_short_id("demo-123")
    assert result is not None
    assert isinstance(result, VulnerabilityCase)
    assert result.id_ == case.id_


def test_find_case_by_short_id_with_urn_case_id(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )

    case = VulnerabilityCase(
        id_="urn:uuid:11111111-2222-3333-4444-555555555555"
    )
    dl.save(case)

    result = dl.find_case_by_short_id("11111111-2222-3333-4444-555555555555")
    assert result is not None
    assert isinstance(result, VulnerabilityCase)
    assert result.id_ == case.id_


def test_find_case_by_short_id_returns_none_when_ambiguous(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )

    case1 = VulnerabilityCase(id_="https://org1.example/api/v2/cases/shared")
    case2 = VulnerabilityCase(id_="https://org2.example/api/v2/cases/shared")
    dl.save(case1)
    dl.save(case2)

    assert dl.find_case_by_short_id("shared") is None


# ---------------------------------------------------------------------------
# find_case_by_report_id tests
# ---------------------------------------------------------------------------


def test_find_case_by_report_id_returns_case_when_report_stored_as_string(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="CVE-2025-001",
        content="Test vulnerability",
        attributed_to="https://example.org/finder",
    )
    case = VulnerabilityCase()
    case.vulnerability_reports.append(report.id_)

    dl.create(report)
    dl.save(case)

    result = dl.find_case_by_report_id(report.id_)
    assert result is not None
    assert isinstance(result, VulnerabilityCase)
    assert result.id_ == case.id_


def test_find_case_by_report_id_returns_case_when_report_stored_as_object(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="CVE-2025-002",
        content="Another vulnerability",
        attributed_to="https://example.org/finder",
    )
    case = VulnerabilityCase()
    case.vulnerability_reports.append(report)

    dl.create(report)
    dl.save(case)

    result = dl.find_case_by_report_id(report.id_)
    assert result is not None
    assert isinstance(result, VulnerabilityCase)
    assert result.id_ == case.id_


def test_find_case_by_report_id_returns_none_when_not_found(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="CVE-2025-003",
        content="Unlinked vulnerability",
        attributed_to="https://example.org/finder",
    )
    case = VulnerabilityCase()

    dl.create(report)
    dl.save(case)

    result = dl.find_case_by_report_id(report.id_)
    assert result is None


def test_find_case_by_report_id_returns_none_when_no_cases(dl):
    result = dl.find_case_by_report_id("urn:uuid:nonexistent-report")
    assert result is None


def test_find_case_by_report_id_returns_none_for_unknown_id(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="CVE-2025-004",
        content="Linked vulnerability",
        attributed_to="https://example.org/finder",
    )
    other_report = VulnerabilityReport(
        name="CVE-2025-005",
        content="Unlinked vulnerability",
        attributed_to="https://example.org/finder",
    )
    case = VulnerabilityCase()
    case.vulnerability_reports.append(report.id_)

    dl.create(report)
    dl.create(other_report)
    dl.save(case)

    result = dl.find_case_by_report_id(other_report.id_)
    assert result is None


def test_find_case_by_report_id_returns_case_via_report_case_link(dl):
    from vultron.core.models.report_case_link import VultronReportCaseLink
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    report = VulnerabilityReport(
        name="CVE-2025-006",
        content="Linked through ReportCaseLink",
        attributed_to="https://example.org/finder",
    )
    case = VulnerabilityCase()

    dl.create(report)
    dl.save(case)
    dl.save(VultronReportCaseLink(report_id=report.id_, case_id=case.id_))

    result = dl.find_case_by_report_id(report.id_)

    assert result is not None
    assert isinstance(result, VulnerabilityCase)
    assert result.id_ == case.id_
