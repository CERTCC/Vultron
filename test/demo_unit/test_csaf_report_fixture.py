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
"""The rv-csaf scenario's CSAF document is schema-valid and says what the scenario checks.

The document is read with the reader the submit-report trigger uses
(:func:`~vultron.wire.csaf.reader.read_submitted_csaf_document`), whose
stage-1 check is the generated models of the pinned CSAF 2.1 revision
(CSAF-04-009), so a schema-valid verdict here is the trigger's own.
"""

from datetime import UTC, datetime, timedelta

import pytest

from vultron.core.models.report_claims import SchemaVerdict
from vultron.demo.helpers.csaf_report import (
    CSAF_DISCLOSURE_AFTER,
    CSAF_REPORT_SUMMARY,
    CSAF_REPORT_TITLE,
    VENDOR_DEFAULT_EMBARGO,
    csaf_date,
    csaf_disclosure_date,
    csaf_vulnerability_report,
)
from vultron.metadata.csaf.pin import load_pin
from vultron.wire.csaf.reader import read_submitted_csaf_document

_WRITTEN = datetime(2026, 11, 11, 9, 30, 15, 123456, tzinfo=UTC)


@pytest.mark.spec("DEMOMA-28-004")
def test_the_document_is_schema_valid_against_the_pinned_revision() -> None:
    reading = read_submitted_csaf_document(
        csaf_vulnerability_report(_WRITTEN)
    ).reading

    assert reading.schema_verdict is SchemaVerdict.SCHEMA_VALID
    assert reading.schema_errors == []
    assert reading.skipped == []


@pytest.mark.spec("DEMOMA-28-004")
def test_the_document_names_the_schema_the_pin_records() -> None:
    """The ``$schema`` is the pinned root's URL, so the check is against the pin."""
    pin = load_pin()
    document = csaf_vulnerability_report(_WRITTEN)

    assert pin.sources[str(document["$schema"])] == pin.root


@pytest.mark.spec("DEMOMA-28-003")
def test_the_document_states_what_the_case_is_checked_against() -> None:
    """Title, summary note and disclosure date are the scenario's M2 and M3."""
    claims = read_submitted_csaf_document(
        csaf_vulnerability_report(_WRITTEN)
    ).reading.claims

    assert claims.document_category == "csaf_vulnerability_report"
    assert claims.name == CSAF_REPORT_TITLE
    assert claims.summary == CSAF_REPORT_SUMMARY
    assert [vul.disclosure_date for vul in claims.vulnerabilities] == [
        csaf_disclosure_date(_WRITTEN)
    ]
    assert [vul.exploitation for vul in claims.vulnerabilities] == [None]


def test_the_disclosure_date_is_the_shorter_term() -> None:
    """Shorter than the Vendor's default, so it wins shortest-wins (EP-04-003)."""
    disclosure = csaf_disclosure_date(_WRITTEN)

    assert CSAF_DISCLOSURE_AFTER < VENDOR_DEFAULT_EMBARGO
    assert disclosure == datetime(2026, 11, 21, 9, 30, 15, tzinfo=UTC)
    assert timedelta(0) < disclosure - _WRITTEN <= CSAF_DISCLOSURE_AFTER


def test_a_csaf_date_is_utc_in_whole_seconds() -> None:
    offset = datetime(2026, 1, 2, 3, 4, 5, 999, tzinfo=UTC).astimezone(
        datetime.now().astimezone().tzinfo
    )

    assert csaf_date(offset) == "2026-01-02T03:04:05Z"


def test_a_naive_date_is_refused() -> None:
    with pytest.raises(ValueError, match="naive"):
        csaf_date(datetime(2026, 1, 2, 3, 4, 5))  # noqa: DTZ001 — the case under test
