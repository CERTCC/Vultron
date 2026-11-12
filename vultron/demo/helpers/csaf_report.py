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
"""The CSAF 2.1 vulnerability report the ``rv-csaf`` scenario's Reporter sends.

This project wrote the document; it is not one of the CSAF Technical
Committee's test documents, which nothing here reads (CSAF-05-004).  It is
schema-valid against the pinned CSAF 2.1 revision (``third_party/csaf/``),
which ``test/demo_unit/test_csaf_report_fixture.py`` checks with the
generated models the submit-report trigger checks it with (CSAF-04-009).

Its dates are the run's: a fixed ``disclosure_date`` would fall in the past
once the calendar passed it, and a past date fills no embargo end
(CSAF-03-003).  So :func:`csaf_vulnerability_report` stamps the release
dates with the instant the Reporter writes the document and the disclosure
date :data:`CSAF_DISCLOSURE_AFTER` later.  That term is shorter than the
Vendor's published default (:data:`VENDOR_DEFAULT_EMBARGO`), so under
shortest-wins the document's date is the active embargo's end and the
Vendor's default is the pending revision (EP-04-003, CSAF-03-001).

The document states no exploitation, so the case starts with P, X and A
clear and takes an embargo (EP-04-020, CSAF-03-006).
"""

from datetime import UTC, datetime, timedelta

from pydantic import JsonValue

#: The document's ``document.title``: the case's name (CSAF-03-007).
CSAF_REPORT_TITLE = "Authentication bypass in the Example Router web console"

#: The document-level ``summary`` note: the case's summary (CSAF-03-007).
CSAF_REPORT_SUMMARY = (
    "A crafted session cookie lets an unauthenticated attacker reach the"
    " router's administrative web console."
)

#: The report's ``content``, which the trigger requires and the document does
#: not fill.
CSAF_REPORT_CONTENT = (
    "The Reporter attaches a CSAF 2.1 vulnerability report describing an"
    " authentication bypass in the Example Router web console."
)

#: How long after the document is written its ``disclosure_date`` falls.
CSAF_DISCLOSURE_AFTER = timedelta(days=10)

#: The Vendor's published default embargo, its actor default (EP-01-002).
#: Longer than :data:`CSAF_DISCLOSURE_AFTER`, so the document's date wins.
VENDOR_DEFAULT_EMBARGO = timedelta(days=30)

#: The ``$schema`` every CSAF 2.1 document names (CSAF-01-003).
_CSAF_21_SCHEMA = "https://docs.oasis-open.org/csaf/csaf/v2.1/schema/csaf.json"


def csaf_date(when: datetime) -> str:
    """Write *when* as a CSAF ``date-time``: UTC, whole seconds, ``Z``.

    Whole seconds, so the date read back from the document is the instant
    the scenario compares the embargo's end with.

    Raises:
        ValueError: *when* is naive, so it names no instant.
    """
    if when.tzinfo is None:
        raise ValueError(f"{when!r} is naive; a CSAF date-time is an instant")
    return (
        when.astimezone(UTC)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def csaf_disclosure_date(written: datetime) -> datetime:
    """The ``disclosure_date`` of a document written at *written*, as an instant."""
    return datetime.fromisoformat(csaf_date(written + CSAF_DISCLOSURE_AFTER))


def csaf_vulnerability_report(written: datetime) -> dict[str, JsonValue]:
    """Return the scenario's CSAF vulnerability report, written at *written*.

    A ``csaf_vulnerability_report`` from the Reporter, as discoverer, about one
    vulnerability, with a document-level ``summary`` note and a
    ``disclosure_date`` :data:`CSAF_DISCLOSURE_AFTER` after *written*.

    Args:
        written: The instant the Reporter writes the document; timezone-aware.

    Returns:
        The document as a JSON object, ready for the submit-report trigger.
    """
    released = csaf_date(written)
    return {
        "$schema": _CSAF_21_SCHEMA,
        "document": {
            "category": "csaf_vulnerability_report",
            "csaf_version": "2.1",
            "distribution": {"tlp": {"label": "AMBER"}},
            "lang": "en",
            "notes": [
                {
                    "category": "summary",
                    "text": CSAF_REPORT_SUMMARY,
                    "title": "Summary",
                },
                {
                    "category": "description",
                    "text": (
                        "The web console accepts any session cookie whose"
                        " signature field is empty, and treats its holder as"
                        " the administrator."
                    ),
                    "title": "Description",
                },
            ],
            "publisher": {
                "category": "discoverer",
                "name": "Example Reporter",
                "namespace": "https://reporter.example.org",
            },
            "title": CSAF_REPORT_TITLE,
            "tracking": {
                "current_release_date": released,
                "id": "EXAMPLE-REPORTER-2026-0001",
                "initial_release_date": released,
                "revision_history": [
                    {
                        "date": released,
                        "number": "1",
                        "summary": "Initial report to the vendor.",
                    }
                ],
                "status": "final",
                "version": "1",
            },
        },
        "vulnerabilities": [
            {
                "title": "Empty cookie signature accepted",
                "disclosure_date": csaf_date(csaf_disclosure_date(written)),
                "notes": [
                    {
                        "category": "description",
                        "text": (
                            "Sending a session cookie with an empty signature"
                            " field grants administrative access."
                        ),
                    }
                ],
            }
        ],
    }


__all__ = [
    "CSAF_DISCLOSURE_AFTER",
    "CSAF_REPORT_CONTENT",
    "CSAF_REPORT_SUMMARY",
    "CSAF_REPORT_TITLE",
    "VENDOR_DEFAULT_EMBARGO",
    "csaf_date",
    "csaf_disclosure_date",
    "csaf_vulnerability_report",
]
