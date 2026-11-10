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
"""The node that fills a new case's inputs from the carried CSAF report."""

from datetime import UTC, datetime, timedelta

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.nodes.proposal_case_inputs import (
    REPORT_CASE_INPUTS_KEY,
    ResolveReportCaseInputsNode,
    csaf_proposed_embargo_id,
    filling_reading,
)
from vultron.core.models.report_claims import (
    ClaimsReading,
    ReportClaims,
    SchemaVerdict,
    VulnerabilityClaims,
)
from vultron.core.services.report_case_inputs import (
    ReportCaseInputs,
    StatedReportFields,
)

_AT = datetime(2026, 11, 1, 12, tzinfo=UTC)
_END = _AT + timedelta(days=20)
_PROPOSAL = "https://vendor.example.org/proposals/1"
_REPORT = "https://finder.example.org/reports/1"


def _reading(category: str, digest: str = "a" * 64) -> ClaimsReading:
    return ClaimsReading(
        document_id=f"{_REPORT}/{digest[:4]}",
        document_digest=digest,
        document_format="CSAF 2.1",
        schema_verdict=SchemaVerdict.SCHEMA_VALID,
        claims=ReportClaims(
            document_category=category,
            name=f"title {category}",
            vulnerabilities=[VulnerabilityClaims(disclosure_date=_END)],
        ),
    )


def _run(node: ResolveReportCaseInputsNode, key: str) -> object:
    result, value = BTTestScenario().run_capturing(node, key, at=_AT)
    assert result.status.name == "SUCCESS", result.feedback_message
    return value


def test_the_first_vulnerability_report_document_is_the_one_that_fills() -> (
    None
):
    advisory = _reading("csaf_security_advisory", "b" * 64)
    first = _reading("csaf_vulnerability_report", "c" * 64)
    second = _reading("csaf_vulnerability_report", "d" * 64)
    assert filling_reading([advisory, first, second]) is first
    assert filling_reading([advisory]) is None


def test_a_csaf_end_is_seeded_as_the_senders_proposal() -> None:
    node = ResolveReportCaseInputsNode(
        report_id=_REPORT,
        proposal_id=_PROPOSAL,
        readings=[_reading("csaf_vulnerability_report")],
        stated=StatedReportFields(),
    )
    embargo = _run(node, "sender_proposed_embargo")
    assert getattr(embargo, "id_", None) == csaf_proposed_embargo_id(_PROPOSAL)
    assert getattr(embargo, "end_time", None) == _END
    assert getattr(embargo, "context", None) == _REPORT


def test_a_proposal_naming_no_report_seeds_no_embargo() -> None:
    node = ResolveReportCaseInputsNode(
        report_id=None,
        proposal_id=_PROPOSAL,
        readings=[_reading("csaf_vulnerability_report")],
        stated=StatedReportFields(),
    )
    assert _run(node, "sender_proposed_embargo") is None
    inputs = _run(
        ResolveReportCaseInputsNode(
            report_id=None,
            proposal_id=_PROPOSAL,
            readings=[_reading("csaf_vulnerability_report")],
            stated=StatedReportFields(),
        ),
        REPORT_CASE_INPUTS_KEY,
    )
    assert isinstance(inputs, ReportCaseInputs)
    assert inputs.name == "title csaf_vulnerability_report"


def test_no_document_passes_the_stated_values_through() -> None:
    node = ResolveReportCaseInputsNode(
        report_id=_REPORT,
        proposal_id=_PROPOSAL,
        readings=[],
        stated=StatedReportFields(name="Report", summary="Text"),
    )
    inputs = _run(node, REPORT_CASE_INPUTS_KEY)
    assert inputs == ReportCaseInputs(name="Report", summary="Text")
