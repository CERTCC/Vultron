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
"""A received report's CSAF attachment is checked, read and recorded, never refused.

Receive-path tests for CSAF-01-003, CSAF-02-005, CSAF-02-006 and CSAF-04-001
to CSAF-04-005: an ``Offer(VulnerabilityReport)`` is built with the factory,
delivered through the parser and extractor as the inbox delivers it, and
handled by ``SubmitReportReceivedUseCase`` in the receiver's own store.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import JsonValue

from test.support.received import received_event
from test.wire.csaf._documents import (
    minimal_csaf_document,
    section,
    vulnerability_report_document,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.bridge.act_instant import act_instant_in_tree_run
from vultron.core.models.actor import VultronService
from vultron.core.models.attached_document import (
    AttachedDocument,
    AttachedImage,
)
from vultron.core.models.events.report import SubmitReportReceivedEvent
from vultron.core.models.report import (
    ReportAttachment,
    VulnerabilityReport,
)
from vultron.core.models.report_claims import (
    ClaimOutcome,
    ReportClaimsRecord,
    SchemaVerdict,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.use_cases.received.report import SubmitReportReceivedUseCase
from vultron.wire.as2.factories.report import rm_submit_report_activity

pytestmark = pytest.mark.usefixtures("case_actor_service_url")

_VENDOR = "https://vendor.example.org/actors/vendor"
_FINDER = "https://finder.example.org/actors/finder"
_REPORT_ID = "https://finder.example.org/reports/widget"
_CSAF_ID = f"{_REPORT_ID}/csaf"
_OTHER_ID = f"{_REPORT_ID}/notes"
_RECEIVED_AT = datetime(2026, 11, 1, 12, tzinfo=UTC)


def _document(content: str, document_id: str = _CSAF_ID) -> AttachedDocument:
    return AttachedDocument(
        id_=document_id, media_type="application/json", content=content
    )


def _csaf(data: dict[str, JsonValue]) -> AttachedDocument:
    return _document(json.dumps(data))


class _Receipt:
    """One delivery of a report Offer to the Vendor, and what it left behind."""

    def __init__(
        self, *attachments: ReportAttachment, report_id: str = _REPORT_ID
    ) -> None:
        self.report_id = report_id
        report = VulnerabilityReport(
            id_=report_id,
            name="Widget overflow",
            content="The widget overflows its buffer.",
            attachment=list(attachments) or None,
        )
        offer = rm_submit_report_activity(report, to=_VENDOR, actor=_FINDER)
        event = received_event(offer, receiving_actor_id=_VENDOR)
        assert isinstance(event, SubmitReportReceivedEvent)
        self.event = event
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR)
        self.dl.save(VultronService(id_=_VENDOR))

    def handle(self) -> HandlerResult:
        # The inbox runs each delivery inside an act (ADR-0176).
        with act_instant_in_tree_run(_RECEIVED_AT):
            return SubmitReportReceivedUseCase(
                self.dl,
                self.event,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def records(self) -> list[ReportClaimsRecord]:
        found = self.dl.list_objects("ReportClaimsRecord")
        assert all(isinstance(r, ReportClaimsRecord) for r in found)
        return [
            r
            for r in found
            if isinstance(r, ReportClaimsRecord)
            and r.report_id == self.report_id
        ]

    def record(self) -> ReportClaimsRecord:
        [only] = self.records()
        return only

    def stored_report(self) -> VulnerabilityReport:
        report = self.dl.read(self.report_id)
        assert isinstance(report, VulnerabilityReport)
        return report

    def sent_bodies(self) -> list[dict[str, Any]]:
        bodies = [
            read_sealed_body_dict(self.dl, activity_id)
            for activity_id in self.dl.outbox_list()
        ]
        assert all(body is not None for body in bodies)
        return [body for body in bodies if body is not None]


def _schema_invalid() -> dict[str, JsonValue]:
    data = vulnerability_report_document()
    section(data, "document", "tracking")["status"] = "unknown-status"
    return data


@pytest.mark.spec("CSAF-01-003")
def test_only_the_csaf_attachment_is_recognized_as_csaf() -> None:
    receipt = _Receipt(
        _document(json.dumps({"title": "not CSAF"}), _OTHER_ID),
        _csaf(vulnerability_report_document()),
    )

    receipt.handle()

    record = receipt.record()
    assert record.reading.document_id == _CSAF_ID
    assert record.reading.document_format == "CSAF 2.1"
    assert record.report_id == _REPORT_ID


def test_a_report_without_csaf_stores_no_claims_record() -> None:
    receipt = _Receipt()

    receipt.handle()

    assert receipt.records() == []


@pytest.mark.spec("CSAF-04-001")
@pytest.mark.parametrize(
    ("data", "verdict"),
    [
        (vulnerability_report_document(), SchemaVerdict.SCHEMA_VALID),
        (_schema_invalid(), SchemaVerdict.SCHEMA_INVALID),
    ],
    ids=["schema-valid", "schema-invalid"],
)
def test_receipt_stores_the_schema_verdict_and_its_errors(
    data: dict[str, JsonValue], verdict: SchemaVerdict
) -> None:
    receipt = _Receipt(_csaf(data))

    receipt.handle()

    reading = receipt.record().reading
    assert reading.schema_verdict is verdict
    if verdict is SchemaVerdict.SCHEMA_VALID:
        assert reading.schema_errors == []
    else:
        assert [e.path for e in reading.schema_errors] == [
            "$.document.tracking.status"
        ]


@pytest.mark.spec("CSAF-04-002")
def test_the_stored_verdict_is_only_ever_schema_valid_or_schema_invalid() -> (
    None
):
    stored = set()
    for index, data in enumerate(
        (vulnerability_report_document(), _schema_invalid())
    ):
        # One store per actor, so each receipt is of a report of its own.
        receipt = _Receipt(_csaf(data), report_id=f"{_REPORT_ID}-{index}")
        receipt.handle()
        raw = receipt.record().model_dump(mode="json")
        stored.add(raw["reading"]["schema_verdict"])

    assert stored == {"schema-valid", "schema-invalid"}


@pytest.mark.spec("CSAF-02-006")
@pytest.mark.parametrize(
    "attachment",
    [
        _csaf(_schema_invalid()),
        _document('{"$schema": "https://docs.oasis-open.org/csaf/csaf/v2.1/'),
        _csaf({**minimal_csaf_document(), "document": "not an object"}),
    ],
    ids=["schema-invalid", "not-json", "unreadable-document"],
)
def test_a_broken_csaf_attachment_never_refuses_the_report(
    attachment: AttachedDocument,
) -> None:
    receipt = _Receipt(attachment)

    result = receipt.handle()

    assert result.disposition is HandlerDisposition.APPLIED
    assert receipt.stored_report().attachment == [attachment]
    assert receipt.sent_bodies(), "the receiver still proposes the case"


@pytest.mark.spec("CSAF-04-003")
def test_a_schema_invalid_document_is_read_field_by_field_and_logs_each_skip(
    caplog: pytest.LogCaptureFixture,
) -> None:
    data = vulnerability_report_document()
    data["vulnerabilities"][0]["disclosure_date"] = "next Tuesday"
    receipt = _Receipt(_csaf(data))

    with caplog.at_level(logging.INFO):
        result = receipt.handle()

    assert result.disposition is HandlerDisposition.APPLIED
    reading = receipt.record().reading
    assert reading.schema_verdict is SchemaVerdict.SCHEMA_INVALID
    [claimed] = reading.claims.vulnerabilities
    assert claimed.disclosure_date is None
    assert claimed.exploitation == "P"
    skip_logs = [
        r
        for r in caplog.records
        if r.levelno == logging.INFO
        and "$.vulnerabilities[0].disclosure_date" in r.getMessage()
    ]
    assert len(skip_logs) == 1
    message = skip_logs[0].getMessage()
    assert receipt.event.activity_id in message
    assert _FINDER in message


@pytest.mark.spec("CSAF-02-005")
def test_an_omitted_field_with_a_schema_default_has_no_stored_value() -> None:
    receipt = _Receipt(_csaf(vulnerability_report_document()))

    receipt.handle()

    record = receipt.record()
    [reference] = record.reading.claims.references
    assert reference.category is None
    stored = record.model_dump(mode="json")
    assert "external" not in json.dumps(stored)


@pytest.mark.spec("CSAF-04-004")
def test_the_report_keeps_a_record_of_what_its_csaf_claimed() -> None:
    attachment = _csaf(vulnerability_report_document())
    receipt = _Receipt(attachment)

    receipt.handle()

    record = receipt.record()
    assert record.activity_id == receipt.event.activity_id
    assert record.received_at == _RECEIVED_AT
    paths = record.reading.claims.value_paths()
    assert "name" in paths
    assert "vulnerabilities[0].disclosure_date" in paths
    assert record.outcomes == dict.fromkeys(paths, ClaimOutcome.DISPLAY_ONLY)
    # The report itself stays as received (VM-08-002).
    report = receipt.stored_report()
    assert report.attachment == [attachment]

    # Each outcome a later step records is kept with the report.
    updated = record.with_outcome(
        "name", ClaimOutcome.OVERRIDDEN
    ).with_outcome("vulnerabilities[0].disclosure_date", ClaimOutcome.APPLIED)
    receipt.dl.save(updated)
    assert receipt.record().outcomes == {
        **record.outcomes,
        "name": ClaimOutcome.OVERRIDDEN,
        "vulnerabilities[0].disclosure_date": ClaimOutcome.APPLIED,
    }


def test_a_resent_offer_keeps_the_record_it_already_wrote() -> None:
    receipt = _Receipt(_csaf(vulnerability_report_document()))
    receipt.handle()
    first = receipt.record()

    receipt.handle()

    assert receipt.record() == first


@pytest.mark.spec("CSAF-04-005")
def test_the_claims_record_is_never_sent() -> None:
    receipt = _Receipt(_csaf(_schema_invalid()))

    receipt.handle()

    record = receipt.record()
    bodies = receipt.sent_bodies()
    assert bodies, "the receipt sends its case proposal"
    sent = json.dumps(bodies)
    assert record.id_ not in sent
    assert "ReportClaimsRecord" not in sent
    for marker in ("schema-invalid", "schema-valid", "display-only"):
        assert marker not in sent


def test_a_resent_offer_whose_document_has_no_id_keeps_one_record() -> None:
    """The parser mints a fresh id for an id-less Document at every parse."""
    content = json.dumps(vulnerability_report_document())
    first = _Receipt(
        AttachedDocument(media_type="application/json", content=content)
    )
    first.handle()
    again = _Receipt(
        AttachedDocument(media_type="application/json", content=content)
    )
    assert (
        again.event.claims_readings[0].document_id
        != first.event.claims_readings[0].document_id
    )
    again.dl = first.dl

    again.handle()

    assert len(first.records()) == 1


def test_two_documents_sharing_an_id_each_get_a_record() -> None:
    other = vulnerability_report_document()
    other["document"]["title"] = "A second advisory"
    receipt = _Receipt(_csaf(vulnerability_report_document()), _csaf(other))

    receipt.handle()

    names = sorted(r.reading.claims.name or "" for r in receipt.records())
    assert names == ["A second advisory", "Buffer overflow in Example Widget"]


def test_an_image_beside_the_csaf_document_is_kept_and_not_read() -> None:
    image = AttachedImage(
        id_=_OTHER_ID, url="https://finder.example.org/shot.png"
    )
    receipt = _Receipt(image, _csaf(vulnerability_report_document()))

    result = receipt.handle()

    assert result.disposition is HandlerDisposition.APPLIED
    assert [r.reading.document_id for r in receipt.records()] == [_CSAF_ID]
    stored = receipt.stored_report().attachment
    assert stored is not None and type(stored[0]) is AttachedImage


@pytest.mark.spec("CSAF-02-006")
@pytest.mark.parametrize(
    "other",
    [
        {"type": "Note", "id": _OTHER_ID, "content": "Steps to reproduce."},
        {"type": "Link", "href": "https://finder.example.org/advisory"},
        "https://finder.example.org/advisory",
    ],
    ids=["note", "link", "bare-uri"],
)
def test_an_attachment_that_is_no_file_never_refuses_the_report(
    other: dict[str, str] | str,
) -> None:
    receipt = _Receipt(other, _csaf(vulnerability_report_document()))

    result = receipt.handle()

    assert result.disposition is HandlerDisposition.APPLIED
    assert [r.reading.document_id for r in receipt.records()] == [_CSAF_ID]
    stored = receipt.stored_report().attachment
    assert stored is not None and len(stored) == 2
    assert type(stored[1]) is AttachedDocument
