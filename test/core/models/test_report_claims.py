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
"""The claims models hold what a document states and what became of each value."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.report_claims import (
    ClaimedAcknowledgment,
    ClaimedReference,
    ClaimOutcome,
    ClaimsReading,
    ReportClaims,
    ReportClaimsRecord,
    SchemaError,
    SchemaVerdict,
    VulnerabilityClaims,
)

_REPORT_ID = "https://reporter.example.org/reports/1"
_DOCUMENT_ID = "https://reporter.example.org/reports/1/csaf"
_DIGEST = "a" * 64
_ACTIVITY_ID = "https://reporter.example.org/activities/offer-1"
_RECEIVER = "https://vendor.example.org/actors/vendor"


def _claims() -> ReportClaims:
    return ReportClaims(
        name="Example advisory",
        references=[ClaimedReference(url="https://example.org/advisory")],
        vulnerabilities=[
            VulnerabilityClaims(
                ids=["CVE-2026-0001"],
                disclosure_date=datetime(2026, 12, 1, tzinfo=UTC),
                first_known_exploitation_dates=[
                    datetime(2026, 9, 30, tzinfo=UTC),
                    datetime(2026, 10, 1, 12, 0, 0, 120000, tzinfo=UTC),
                ],
            )
        ],
    )


def _reading(**overrides) -> ClaimsReading:
    fields = {
        "document_id": _DOCUMENT_ID,
        "document_digest": _DIGEST,
        "document_format": "CSAF 2.1",
        "schema_verdict": SchemaVerdict.SCHEMA_VALID,
        "claims": _claims(),
        **overrides,
    }
    return ClaimsReading(**fields)


def _record(**overrides) -> ReportClaimsRecord:
    return ReportClaimsRecord(
        report_id=_REPORT_ID,
        activity_id=_ACTIVITY_ID,
        reading=_reading(),
        **overrides,
    )


def test_the_value_paths_name_each_stated_value() -> None:
    assert _claims().value_paths() == [
        "name",
        "references[0]",
        "vulnerabilities[0].ids[0]",
        "vulnerabilities[0].disclosure_date",
        "vulnerabilities[0].first_known_exploitation_dates[0]",
        "vulnerabilities[0].first_known_exploitation_dates[1]",
    ]


@pytest.mark.spec("CSAF-04-002")
def test_the_verdict_is_one_of_two_values() -> None:
    with pytest.raises(ValidationError):
        _reading(schema_verdict="valid")
    with pytest.raises(ValidationError):
        _reading(schema_verdict="valid-csaf")


@pytest.mark.spec("CSAF-04-001")
def test_a_schema_invalid_verdict_needs_its_errors() -> None:
    with pytest.raises(ValidationError, match="CSAF-04-001"):
        _reading(schema_verdict=SchemaVerdict.SCHEMA_INVALID)


@pytest.mark.spec("CSAF-04-001")
def test_a_schema_valid_verdict_carries_no_error() -> None:
    error = SchemaError(path="$.document", message="Field required")
    with pytest.raises(ValidationError, match="CSAF-04-001"):
        _reading(schema_errors=[error])

    invalid = _reading(
        schema_verdict=SchemaVerdict.SCHEMA_INVALID, schema_errors=[error]
    )
    assert invalid.schema_errors == [error]


@pytest.mark.spec("CSAF-04-004")
def test_every_value_read_starts_display_only() -> None:
    record = _record()

    assert record.outcomes == dict.fromkeys(
        _claims().value_paths(), ClaimOutcome.DISPLAY_ONLY
    )


@pytest.mark.spec("CSAF-04-004")
def test_an_outcome_for_a_value_never_claimed_is_refused() -> None:
    with pytest.raises(ValidationError, match="CSAF-04-004"):
        _record(outcomes={"summary": ClaimOutcome.APPLIED})


@pytest.mark.spec("CSAF-04-004")
def test_each_outcome_is_recorded_and_survives_the_store() -> None:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    record = (
        _record()
        .with_outcome("name", ClaimOutcome.OVERRIDDEN)
        .with_outcome(
            "vulnerabilities[0].disclosure_date", ClaimOutcome.APPLIED
        )
    )

    dl.create(record)
    stored = dl.read(record.id_)

    assert stored == record
    assert isinstance(stored, ReportClaimsRecord)
    assert stored.outcomes["name"] is ClaimOutcome.OVERRIDDEN
    assert (
        stored.outcomes["vulnerabilities[0].disclosure_date"]
        is ClaimOutcome.APPLIED
    )
    assert stored.outcomes["references[0]"] is ClaimOutcome.DISPLAY_ONLY


def test_with_outcome_refuses_a_path_that_names_no_value() -> None:
    with pytest.raises(KeyError):
        _record().with_outcome("summary", ClaimOutcome.APPLIED)


def test_the_record_id_derives_from_the_report_and_the_content_digest() -> (
    None
):
    record = _record()

    assert record.id_ == ReportClaimsRecord.build_id(_REPORT_ID, _DIGEST)
    assert record.with_outcome("name", ClaimOutcome.APPLIED).id_ == record.id_


def test_a_claimed_date_serializes_in_the_fixed_form() -> None:
    dumped = _claims().vulnerabilities[0].model_dump(mode="json")

    assert dumped["first_known_exploitation_dates"] == [
        "2026-09-30T00:00:00.000000+00:00",
        "2026-10-01T12:00:00.120000+00:00",
    ]
    assert dumped["disclosure_date"] == "2026-12-01T00:00:00.000000+00:00"


def test_a_blank_claimed_value_is_refused() -> None:
    with pytest.raises(ValidationError):
        ReportClaims(name=" ")


def test_an_acknowledgment_that_names_no_one_is_refused() -> None:
    with pytest.raises(ValidationError):
        ClaimedAcknowledgment()

    assert ClaimedAcknowledgment(organization="Example CERT").names == []


@pytest.mark.parametrize(
    "overrides",
    [{"report_id": 5}, {"outcomes": ["name"]}],
    ids=["report-id-not-string", "outcomes-not-mapping"],
)
def test_a_malformed_record_is_refused(overrides) -> None:
    fields = {
        "report_id": _REPORT_ID,
        "activity_id": _ACTIVITY_ID,
        "reading": _reading().model_dump(),
        **overrides,
    }
    with pytest.raises(ValidationError):
        ReportClaimsRecord(**fields)
