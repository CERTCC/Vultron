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
"""The report receiver's conversion of a report into its proposal (CP-01-026)."""

from datetime import UTC, datetime, timedelta

import pytest

from test.support.act_clock import no_clock
from test.support.objects import make
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.report_claims import (
    ClaimOutcome,
    ClaimsReading,
    ReportClaims,
    SchemaVerdict,
    VulnerabilityClaims,
)
from vultron.core.services.report_case_proposal import (
    ConvertedCaseProposal,
    case_proposal_from_report,
    used_claims,
)
from vultron.enums.roles import CVDRole

_AT = datetime(2026, 11, 1, 12, tzinfo=UTC)
_PAST = _AT - timedelta(days=3)
_VENDOR = "https://vendor.example.org/actors/vendor"
_CASE_ACTOR = "https://case.example.org/actors/case-actor"
_REPORT = "https://finder.example.org/reports/1"
_OFFER = "https://finder.example.org/offers/1"


def _report(name: str | None = None) -> VulnerabilityReport:
    return make(
        VulnerabilityReport, id_=_REPORT, name=name, content="It overflows."
    )


def _reading(
    category: str = "csaf_vulnerability_report", digest: str = "a" * 64
) -> ClaimsReading:
    return ClaimsReading(
        document_id=f"{_REPORT}/{digest[:4]}",
        document_digest=digest,
        document_format="CSAF 2.1",
        schema_verdict=SchemaVerdict.SCHEMA_VALID,
        claims=ReportClaims(
            document_category=category,
            name=f"title {digest[:4]}",
            vulnerabilities=[
                VulnerabilityClaims(cve="CVE-2026-0001", disclosure_date=_PAST)
            ],
        ),
    )


def _convert(
    *readings: ClaimsReading,
    name: str | None = None,
    report: VulnerabilityReport | None = None,
) -> ConvertedCaseProposal:
    return case_proposal_from_report(
        report or _report(name),
        proposer_id=_VENDOR,
        case_actor_id=_CASE_ACTOR,
        readings=readings,
        offer_id=_OFFER,
        proposer_case_roles=[CVDRole.VENDOR],
        at=_AT,
    )


@pytest.mark.spec("CP-01-026", "CP-01-023", "CP-01-027")
def test_the_first_report_document_fills_the_case_inputs() -> None:
    """Only the first ``csaf_vulnerability_report`` reading fills them, and
    its passed disclosure date is carried as the document states it."""
    first, second = _reading(digest="a" * 64), _reading(digest="b" * 64)

    converted = _convert(_reading("csaf_security_advisory"), first, second)

    inputs = converted.proposal.case_inputs
    assert inputs is not None
    assert inputs.name == "title aaaa"
    assert inputs.disclosure_date == _PAST
    assert converted.reading is first
    reading, outcomes = used_claims(_report(), [first, second])
    assert reading is first
    assert (
        outcomes["vulnerabilities[0].disclosure_date"] is ClaimOutcome.APPLIED
    )


@pytest.mark.spec("CSAF-02-003")
def test_the_reports_own_name_beats_the_documents() -> None:
    converted = _convert(_reading(), name="Widget overflow")

    assert converted.proposal.case_inputs is not None
    assert converted.proposal.case_inputs.name == "Widget overflow"
    _, outcomes = used_claims(_report("Widget overflow"), [_reading()])
    assert outcomes["name"] is ClaimOutcome.OVERRIDDEN


@pytest.mark.spec("CP-01-026")
@pytest.mark.parametrize(
    "readings",
    [(), (_reading("csaf_security_advisory"),)],
    ids=["no-reading", "another-category"],
)
def test_no_report_document_states_no_case_inputs(
    readings: tuple[ClaimsReading, ...],
) -> None:
    converted = _convert(*readings)

    assert converted.proposal.case_inputs is None
    assert converted.reading is None
    assert used_claims(_report(), readings) == (None, {})


@pytest.mark.spec("CP-01-003", "CP-01-005", "CP-01-007", "CP-01-013")
def test_the_proposal_names_its_parties_and_the_offer() -> None:
    proposal = _convert().proposal

    assert proposal.attributed_to == _VENDOR
    assert proposal.target == _CASE_ACTOR
    assert proposal.in_reply_to == _OFFER
    assert proposal.proposer_case_roles == [CVDRole.VENDOR]
    assert getattr(proposal.object_, "id_", None) == _REPORT
    # Authored at the act's instant (ADR-0176).
    assert (proposal.published, proposal.updated) == (_AT, _AT)


@pytest.mark.spec("CP-01-023")
def test_the_conversion_reads_no_clock() -> None:
    """A pure function of the instant it is given (ADR-0176)."""
    report, reading = _report(), _reading()
    with no_clock():
        converted = _convert(reading, report=report)

    assert converted.proposal.published == _AT
