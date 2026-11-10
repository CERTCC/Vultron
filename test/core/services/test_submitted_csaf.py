#!/usr/bin/env python

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
"""The submit-report trigger's check of a submitted CSAF document (CSAF-04-009)."""

import pytest
from pydantic import ValidationError

from vultron.core.models.attached_document import AttachedDocument
from vultron.core.models.report_claims import (
    MAX_CSAF_CONTENT_CHARS,
    ClaimsReading,
    ReportClaims,
    SchemaError,
    SchemaVerdict,
    SubmittedCsafDocument,
    csaf_document_text,
)
from vultron.core.services.submitted_csaf import (
    CSAF_DOCUMENT_FIELD,
    submitted_csaf_violations,
)
from vultron.errors import VultronValidationError

_REPORT = "csaf_vulnerability_report"


def _submission(
    *,
    content: str = '{"document": {}}',
    category: str | None = _REPORT,
    errors: tuple[SchemaError, ...] = (),
) -> SubmittedCsafDocument:
    attachment = AttachedDocument(
        media_type="application/json", content=content
    )
    return SubmittedCsafDocument(
        attachment=attachment,
        reading=ClaimsReading(
            document_id=attachment.id_,
            document_digest="0" * 64,
            document_format="CSAF 2.1",
            schema_verdict=(
                SchemaVerdict.SCHEMA_INVALID
                if errors
                else SchemaVerdict.SCHEMA_VALID
            ),
            schema_errors=list(errors),
            claims=ReportClaims(document_category=category),
        ),
    )


def test_a_schema_valid_vulnerability_report_has_no_fault() -> None:
    assert submitted_csaf_violations(_submission()) == []


@pytest.mark.spec("CSAF-04-009")
def test_each_schema_error_is_a_fault_at_its_path() -> None:
    errors = (
        SchemaError(path="$.document.title", message="Field required"),
        SchemaError(path="$.vulnerabilities[0].cve", message="bad pattern"),
    )

    violations = submitted_csaf_violations(_submission(errors=errors))

    assert [v.message.split(":")[0] for v in violations] == [
        "$.document.title",
        "$.vulnerabilities[0].cve",
    ]
    assert all(v.dimensions == (CSAF_DOCUMENT_FIELD,) for v in violations)


@pytest.mark.spec("CSAF-04-009")
@pytest.mark.parametrize(
    ("category", "named"),
    [("csaf_base", "'csaf_base'"), (None, "states no document.category")],
)
def test_any_other_category_is_a_fault(category, named) -> None:
    (violation,) = submitted_csaf_violations(_submission(category=category))

    assert named in violation.message


def test_content_a_receiver_would_not_read_is_refused() -> None:
    content = '{"document": {}}'
    padded = content + " " * (MAX_CSAF_CONTENT_CHARS - len(content) + 1)

    with pytest.raises(ValidationError, match=str(MAX_CSAF_CONTENT_CHARS)):
        _submission(content=padded)


def test_content_at_the_limit_is_no_fault() -> None:
    content = '{"document": {}}'
    padded = content + " " * (MAX_CSAF_CONTENT_CHARS - len(content))

    assert submitted_csaf_violations(_submission(content=padded)) == []


@pytest.mark.parametrize(
    ("document", "match"),
    [
        ({"title": "\ud800"}, "not valid Unicode"),
        ({"pad": "x" * MAX_CSAF_CONTENT_CHARS}, "more than"),
    ],
    ids=["lone-surrogate", "too-long"],
)
def test_unsendable_document_text_is_refused(document, match) -> None:
    with pytest.raises(VultronValidationError, match=match):
        csaf_document_text(document)


def test_document_text_is_the_json_of_the_document() -> None:
    assert csaf_document_text({"title": "Ünïcode"}) == '{"title": "Ünïcode"}'


def test_every_fault_is_reported_together() -> None:
    violations = submitted_csaf_violations(
        _submission(
            category="csaf_base",
            errors=(SchemaError(path="$.document", message="bad"),),
        )
    )

    assert len(violations) == 2


def test_the_reading_must_be_of_the_attachment() -> None:
    submission = _submission()

    with pytest.raises(ValidationError, match="not the attachment"):
        SubmittedCsafDocument(
            attachment=AttachedDocument(
                media_type="application/json", content="{}"
            ),
            reading=submission.reading,
        )


@pytest.mark.parametrize(
    ("media_type", "content", "match"),
    [
        ("text/plain", "{}", "application/json"),
        ("application/json", None, "JSON text"),
    ],
)
def test_the_attachment_must_be_json_text(media_type, content, match) -> None:
    attachment = AttachedDocument(media_type=media_type, content=content)
    reading = _submission().reading.model_copy(
        update={"document_id": attachment.id_}
    )

    with pytest.raises(ValidationError, match=match):
        SubmittedCsafDocument(attachment=attachment, reading=reading)
