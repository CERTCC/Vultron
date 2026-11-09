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
"""The CSAF reader recognizes, checks and reads an attached CSAF 2.1 document."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

import pytest

from test.wire.csaf._documents import (
    minimal_csaf_document,
    section,
    vulnerability_report_document,
)
from vultron.core.models.attached_document import AttachedDocument
from vultron.core.models.report_claims import (
    ClaimedAcknowledgment,
    ClaimedReference,
    SchemaVerdict,
)
from vultron.wire.csaf.models import CommonSecurityAdvisoryFramework
from vultron.wire.csaf.reader import (
    CSAF_21_FORMAT,
    is_csaf_21,
    read_csaf_document,
    read_report_attachments,
)

_DOCUMENT_ID = "https://reporter.example.org/reports/1/csaf"
_ACTIVITY_ID = "https://reporter.example.org/activities/offer-1"
_ACTOR_ID = "https://reporter.example.org/actors/reporter"


def _attachment(
    content: str, document_id: str = _DOCUMENT_ID
) -> AttachedDocument:
    return AttachedDocument(
        id_=document_id, media_type="application/json", content=content
    )


def _read(*attachments: AttachedDocument):
    return read_report_attachments(
        list(attachments), activity_id=_ACTIVITY_ID, actor_id=_ACTOR_ID
    )


def _vul(data: dict[str, Any]) -> dict[str, Any]:
    first = data["vulnerabilities"][0]
    assert isinstance(first, dict)
    return first


# --- recognition (CSAF-01-003) ----------------------------------------------


@pytest.mark.spec("CSAF-01-003")
def test_a_csaf_21_document_is_recognized_by_its_schema_and_version() -> None:
    assert is_csaf_21(minimal_csaf_document())


@pytest.mark.spec("CSAF-01-003")
@pytest.mark.parametrize(
    "edit",
    [
        lambda d: d.update({"$schema": "https://example.org/other.json"}),
        lambda d: d.pop("$schema"),
        lambda d: section(d, "document").update({"csaf_version": "2.0"}),
        lambda d: section(d, "document").pop("csaf_version"),
        lambda d: d.update({"document": "not an object"}),
    ],
    ids=[
        "other-schema",
        "no-schema",
        "csaf-2.0",
        "no-version",
        "document-not-object",
    ],
)
def test_a_document_that_does_not_say_csaf_21_is_not_recognized(edit) -> None:
    data = minimal_csaf_document()
    edit(data)

    assert not is_csaf_21(data)


@pytest.mark.spec("CSAF-01-003")
def test_only_the_csaf_attachment_of_a_report_is_read() -> None:
    readings = _read(
        _attachment(json.dumps({"name": "not CSAF"}), "https://x.example/1"),
        _attachment(json.dumps(minimal_csaf_document())),
        _attachment("[1, 2, 3]", "https://x.example/3"),
    )

    assert [r.document_id for r in readings] == [_DOCUMENT_ID]
    assert readings[0].document_format == CSAF_21_FORMAT


def test_an_attachment_without_content_is_passed_over() -> None:
    assert _read(AttachedDocument(id_=_DOCUMENT_ID)) == []
    assert (
        read_report_attachments(
            None, activity_id=_ACTIVITY_ID, actor_id=_ACTOR_ID
        )
        == []
    )


@pytest.mark.spec("CSAF-02-006")
def test_an_unparseable_attachment_yields_no_reading_and_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="vultron.wire.csaf.reader"):
        readings = _read(_attachment('{"$schema": "https://docs.oasis'))

    assert readings == []
    [record] = [r for r in caplog.records if r.levelno == logging.INFO]
    assert _DOCUMENT_ID in record.getMessage()
    assert _ACTIVITY_ID in record.getMessage()
    assert _ACTOR_ID in record.getMessage()


# --- the schema verdict (CSAF-04-001, CSAF-04-002) ----------------------------


@pytest.mark.spec("CSAF-04-001")
def test_a_schema_valid_document_reads_schema_valid_with_no_errors() -> None:
    reading = read_csaf_document(_DOCUMENT_ID, vulnerability_report_document())

    assert reading.schema_verdict is SchemaVerdict.SCHEMA_VALID
    assert reading.schema_errors == []
    assert reading.skipped == []


@pytest.mark.spec("CSAF-04-001")
def test_a_schema_invalid_document_reads_schema_invalid_with_each_error() -> (
    None
):
    data = vulnerability_report_document()
    section(data, "document", "tracking")["status"] = "unknown-status"
    section(data, "document", "distribution", "tlp")["label"] = "PURPLE"

    reading = read_csaf_document(_DOCUMENT_ID, data)

    assert reading.schema_verdict is SchemaVerdict.SCHEMA_INVALID
    paths = {error.path for error in reading.schema_errors}
    assert "$.document.tracking.status" in paths
    assert "$.document.distribution.tlp.label" in paths
    assert all(error.message for error in reading.schema_errors)


@pytest.mark.spec("CSAF-04-002")
def test_the_verdict_names_only_the_schema() -> None:
    assert {verdict.value for verdict in SchemaVerdict} == {
        "schema-valid",
        "schema-invalid",
    }


# --- reading the claims (CSAF-02-005, CSAF-04-003) ----------------------------


def test_a_schema_valid_document_reads_every_claim_field() -> None:
    claims = read_csaf_document(
        _DOCUMENT_ID, vulnerability_report_document()
    ).claims

    assert claims.document_category == "csaf_vulnerability_report"
    assert claims.name == "Buffer overflow in Example Widget"
    assert claims.summary == "A short summary."
    assert claims.known_affected_vendors == ["Example Vendor"]
    assert claims.distribution_label == "CLEAR"
    assert claims.acknowledgments == [
        ClaimedAcknowledgment(
            names=["Pat Finder"], summary="Found the overflow."
        )
    ]
    [vul] = claims.vulnerabilities
    assert vul.ids == ["CVE-2026-0001"]
    assert vul.title == "Widget overflow"
    assert vul.disclosure_date == datetime(2026, 12, 1, tzinfo=UTC)
    assert vul.exploitation == "P"
    assert vul.first_known_exploitation_dates == [
        datetime(2026, 9, 30, tzinfo=UTC)
    ]


def test_the_summary_falls_back_to_the_description_note() -> None:
    data = vulnerability_report_document()
    section(data, "document")["notes"] = [
        {"category": "description", "text": "A longer description."},
        {"category": "details", "text": "Not a summary."},
    ]

    claims = read_csaf_document(_DOCUMENT_ID, data).claims

    assert claims.summary == "A longer description."


@pytest.mark.spec("CSAF-02-005")
def test_a_field_the_schema_defaults_is_no_claim_when_omitted() -> None:
    data = vulnerability_report_document()
    # The reference states no category; the schema defaults it to external.
    assert (
        CommonSecurityAdvisoryFramework.model_validate(
            data
        ).document.references
        is not None
    )

    claims = read_csaf_document(_DOCUMENT_ID, data).claims

    assert claims.references == [
        ClaimedReference(
            url="https://reporter.example.org/widget",
            summary="The reporter's write-up",
        )
    ]
    assert claims.references[0].category is None


@pytest.mark.spec("CSAF-02-005")
def test_a_schema_default_is_not_claimed_from_an_invalid_document_either() -> (
    None
):
    data = vulnerability_report_document()
    section(data, "document")["unknown_property"] = "makes it schema-invalid"

    reading = read_csaf_document(_DOCUMENT_ID, data)

    assert reading.schema_verdict is SchemaVerdict.SCHEMA_INVALID
    assert reading.claims.references[0].category is None


@pytest.mark.spec("CSAF-02-005")
def test_an_omitted_field_is_no_claim() -> None:
    claims = read_csaf_document(_DOCUMENT_ID, minimal_csaf_document()).claims

    assert claims.summary is None
    assert claims.references == []
    assert claims.vulnerabilities == []
    assert claims.known_affected_vendors == []
    assert claims.acknowledgments == []
    assert claims.involved_parties == []
    assert claims.value_paths() == [
        "document_category",
        "name",
        "distribution_label",
    ]


@pytest.mark.spec("CSAF-04-003")
def test_a_schema_invalid_document_is_read_field_by_field() -> None:
    data = vulnerability_report_document()
    _vul(data)["disclosure_date"] = "next Tuesday"

    reading = read_csaf_document(_DOCUMENT_ID, data)

    assert reading.schema_verdict is SchemaVerdict.SCHEMA_INVALID
    [vul] = reading.claims.vulnerabilities
    assert vul.disclosure_date is None
    assert vul.exploitation == "P"
    assert reading.claims.name == "Buffer overflow in Example Widget"
    assert [s.path for s in reading.skipped] == [
        "$.vulnerabilities[0].disclosure_date"
    ]


@pytest.mark.spec("CSAF-04-003")
@pytest.mark.parametrize(
    ("edit", "skipped_path"),
    [
        (
            lambda d: section(d, "document").update({"title": 7}),
            "$.document.title",
        ),
        (
            lambda d: section(d, "document").update({"title": " "}),
            "$.document.title",
        ),
        (
            lambda d: section(d, "document").update({"notes": "x"}),
            "$.document.notes",
        ),
        (lambda d: d.update({"vulnerabilities": {}}), "$.vulnerabilities"),
        (
            lambda d: d.update({"vulnerabilities": ["x"]}),
            "$.vulnerabilities[0]",
        ),
        (
            lambda d: _vul(d)["first_known_exploitation_dates"][0].update(
                {"exploitation_date": "2026-09-30T00:00:00"}
            ),
            "$.vulnerabilities[0].first_known_exploitation_dates[0]"
            ".exploitation_date",
        ),
        (
            lambda d: _vul(d)["product_status"].update(
                {"known_affected": ["WIDGET-1", 3]}
            ),
            "$.vulnerabilities[0].product_status.known_affected",
        ),
        (
            lambda d: section(d, "document").update(
                {"references": [{"summary": "no url"}]}
            ),
            "$.document.references[0]",
        ),
        (lambda d: d.update({"product_tree": []}), "$.product_tree"),
        (
            lambda d: section(d, "document").update(
                {"references": [{"summary": "s", "url": 5}]}
            ),
            "$.document.references[0].url",
        ),
        (
            lambda d: _vul(d)["product_status"].update(
                {"known_affected": "WIDGET-1"}
            ),
            "$.vulnerabilities[0].product_status.known_affected",
        ),
        (
            lambda d: section(d, "document").update(
                {"acknowledgments": [{"names": []}]}
            ),
            "$.document.acknowledgments[0]",
        ),
        (
            lambda d: section(d, "document", "distribution").update(
                {"tlp": "CLEAR"}
            ),
            "$.document.distribution.tlp",
        ),
    ],
    ids=[
        "title-not-string",
        "title-blank",
        "notes-not-list",
        "vulnerabilities-not-list",
        "vulnerability-not-object",
        "naive-exploitation-date",
        "product-id-not-string",
        "reference-without-url",
        "product-tree-not-object",
        "reference-url-not-string",
        "known-affected-not-list",
        "acknowledgment-naming-no-one",
        "tlp-not-object",
    ],
)
def test_each_unreadable_field_is_skipped_and_named(
    edit, skipped_path
) -> None:
    data = vulnerability_report_document()
    edit(data)

    reading = read_csaf_document(_DOCUMENT_ID, data)

    assert skipped_path in [s.path for s in reading.skipped]
    assert all(s.reason for s in reading.skipped)


def test_several_exploitation_values_are_no_single_claim() -> None:
    data = vulnerability_report_document()
    metric = _vul(data)["metrics"][0]
    metric["content"]["ssvc_v2"]["selections"][0]["values"] = [
        {"key": "P"},
        {"key": "A"},
    ]

    reading = read_csaf_document(_DOCUMENT_ID, data)

    assert reading.claims.vulnerabilities[0].exploitation is None
    assert [s.path for s in reading.skipped] == [
        "$.vulnerabilities[0].metrics"
    ]


def test_a_selection_other_than_ssvc_exploitation_is_not_read() -> None:
    data = vulnerability_report_document()
    selection = _vul(data)["metrics"][0]["content"]["ssvc_v2"]["selections"][0]
    selection["key"] = "A"

    reading = read_csaf_document(_DOCUMENT_ID, data)

    assert reading.claims.vulnerabilities[0].exploitation is None


def test_the_cve_comes_first_among_the_vulnerability_ids() -> None:
    data = vulnerability_report_document()
    _vul(data)["ids"] = [
        {"system_name": "Example tracker", "text": "EX-17"},
        {"system_name": "CVE", "text": "CVE-2026-0001"},
    ]

    [vul] = read_csaf_document(_DOCUMENT_ID, data).claims.vulnerabilities

    assert vul.ids == ["CVE-2026-0001", "EX-17"]


def test_each_known_affected_vendor_is_named_once() -> None:
    data = vulnerability_report_document()
    data["product_tree"]["branches"].append(
        {
            "category": "vendor",
            "name": "Other Vendor",
            "branches": [
                {
                    "category": "product_name",
                    "name": "Gadget",
                    "product": {"name": "Gadget", "product_id": "GADGET-1"},
                },
                {
                    "category": "product_name",
                    "name": "Gizmo",
                    "product": {"name": "Gizmo", "product_id": "GIZMO-1"},
                },
            ],
        }
    )
    # A product under no vendor branch has no vendor to name.
    data["product_tree"]["branches"].append(
        {
            "category": "product_name",
            "name": "Orphan",
            "product": {"name": "Orphan", "product_id": "ORPHAN-1"},
        }
    )
    _vul(data)["product_status"]["known_affected"] = [
        "ORPHAN-1",
        "GADGET-1",
        "WIDGET-1",
        "GIZMO-1",
        "UNLISTED-1",
    ]

    claims = read_csaf_document(_DOCUMENT_ID, data).claims

    assert claims.known_affected_vendors == ["Other Vendor", "Example Vendor"]


def test_the_involved_parties_are_read_by_name() -> None:
    data = vulnerability_report_document()
    section(data, "document")["involvement"] = {
        "actions": [],
        "entities": [
            {
                "category": "vendor",
                "entity_id": "e-1",
                "name": "Example Vendor",
            },
            {"category": "coordinator", "entity_id": "e-2"},
            {
                "category": "vendor",
                "entity_id": "e-3",
                "name": "Example Vendor",
            },
        ],
    }

    claims = read_csaf_document(_DOCUMENT_ID, data).claims

    assert claims.involved_parties == ["Example Vendor"]
