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
"""A report's attachments are core documents that survive the store unchanged."""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.attached_document import AttachedDocument
from vultron.core.models.report import VulnerabilityReport
from vultron.wire.as2.parser import parse_activity

_RECEIVER = "https://vendor.example.org/actors/vendor"
_REPORT_ID = "https://reporter.example.org/reports/1"


def _offer_body(attachment: object) -> dict[str, object]:
    return {
        "@context": ["https://www.w3.org/ns/activitystreams"],
        "type": "Offer",
        "id": "https://reporter.example.org/activities/offer-1",
        "actor": "https://reporter.example.org/actors/reporter",
        "to": [_RECEIVER],
        "published": "2026-11-01T00:00:00+00:00",
        "object": {
            "type": "VulnerabilityReport",
            "id": _REPORT_ID,
            "name": "Widget overflow",
            "content": "The widget overflows.",
            "published": "2026-11-01T00:00:00+00:00",
            "attachment": attachment,
        },
    }


def _parsed_report(attachment: object) -> VulnerabilityReport:
    report = getattr(parse_activity(_offer_body(attachment)), "object_", None)
    assert isinstance(report, VulnerabilityReport)
    return report


def test_a_received_reports_attachments_are_core_documents() -> None:
    report = _parsed_report(
        [
            {
                "type": "Document",
                "id": f"{_REPORT_ID}/csaf",
                "mediaType": "application/json",
                "content": '{"document": {}}',
            }
        ]
    )

    assert report.attachment is not None
    [document] = report.attachment
    assert type(document) is AttachedDocument
    assert document.media_type == "application/json"
    assert document.content == '{"document": {}}'


def test_a_reports_attachments_survive_save_and_read_unchanged() -> None:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    report = _parsed_report(
        [
            {
                "type": "Document",
                "id": f"{_REPORT_ID}/csaf",
                "mediaType": "application/json",
                "content": '{"document": {}}',
            },
            {"type": "Document", "content": "a second document, no id"},
        ]
    )

    dl.create(report)
    stored = dl.read(_REPORT_ID)

    assert stored == report
    assert isinstance(stored, VulnerabilityReport)
    assert stored.attachment is not None
    assert all(type(d) is AttachedDocument for d in stored.attachment)


def test_a_report_without_attachments_publishes_none() -> None:
    report = VulnerabilityReport(id_=_REPORT_ID, content="text")

    assert report.attachment is None
    assert "attachment" not in report.model_dump(
        by_alias=True, exclude_none=True
    )


@pytest.mark.parametrize(
    "attachment",
    [[{"type": "Note", "content": "not a document"}], ["https://x.example/a"]],
    ids=["note", "bare-link"],
)
def test_an_attachment_that_is_no_document_is_refused_at_the_edge(
    attachment: object,
) -> None:
    from vultron.wire.as2.errors import VultronParseValidationError

    with pytest.raises(VultronParseValidationError):
        parse_activity(_offer_body(attachment))
