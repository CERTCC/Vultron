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
"""Hand-written CSAF 2.1 documents for tests.

The suite never reads the CSAF Technical Committee's test documents
(CSAF-05-004), so tests build their own.
"""

from typing import Any

from pydantic import JsonValue


def minimal_csaf_document() -> dict[str, JsonValue]:
    """Return a schema-valid CSAF 2.1 document with only the required fields."""
    released = "2026-10-01T00:00:00Z"
    return {
        "$schema": "https://docs.oasis-open.org/csaf/csaf/v2.1/schema/csaf.json",
        "document": {
            "category": "csaf_base",
            "csaf_version": "2.1",
            "distribution": {"tlp": {"label": "CLEAR"}},
            "publisher": {
                "category": "coordinator",
                "name": "Example Coordinator",
                "namespace": "https://coordinator.example.org",
            },
            "title": "Example advisory",
            "tracking": {
                "current_release_date": released,
                "id": "EXAMPLE-2026-0001",
                "initial_release_date": released,
                "revision_history": [
                    {
                        "date": released,
                        "number": "1",
                        "summary": "Initial version.",
                    }
                ],
                "status": "final",
                "version": "1",
            },
        },
    }


def vulnerability_report_document() -> dict[str, Any]:
    """Return a schema-valid ``csaf_vulnerability_report`` with every claim field.

    It states a title, a document-level ``summary`` and ``description`` note,
    an acknowledgment,
    a reference with no ``category`` (which the schema defaults to
    ``external``), one vendor's known-affected product, and one vulnerability
    with a CVE, another tracking ID, a note, a reference, a disclosure date,
    an SSVC Exploitation selection and a first known exploitation date.
    """
    data: dict[str, Any] = minimal_csaf_document()
    document = section(data, "document")
    document["category"] = "csaf_vulnerability_report"
    document["title"] = "Buffer overflow in Example Widget"
    document["notes"] = [
        {"category": "description", "text": "A longer description."},
        {"category": "summary", "text": "A short summary."},
    ]
    document["acknowledgments"] = [
        {"names": ["Pat Finder"], "summary": "Found the overflow."}
    ]
    document["references"] = [
        {
            "summary": "The reporter's write-up",
            "url": "https://reporter.example.org/widget",
        }
    ]
    data["product_tree"] = {
        "branches": [
            {
                "category": "vendor",
                "name": "Example Vendor",
                "branches": [
                    {
                        "category": "product_name",
                        "name": "Example Widget",
                        "product": {
                            "name": "Example Vendor Example Widget",
                            "product_id": "WIDGET-1",
                        },
                    }
                ],
            }
        ]
    }
    data["vulnerabilities"] = [
        {
            "cve": "CVE-2026-0001",
            "ids": [{"system_name": "Example tracker", "text": "EX-17"}],
            "title": "Widget overflow",
            "notes": [
                {
                    "category": "description",
                    "text": "The widget overflows its buffer.",
                    "title": "What goes wrong",
                }
            ],
            "references": [
                {
                    "summary": "The vendor's bulletin",
                    "url": "https://vendor.example.org/bulletins/17",
                }
            ],
            "disclosure_date": "2026-12-01T00:00:00Z",
            "first_known_exploitation_dates": [
                {
                    "date": "2026-10-02T00:00:00Z",
                    "exploitation_date": "2026-09-30T00:00:00Z",
                }
            ],
            "metrics": [
                {
                    "content": {
                        "ssvc_v2": {
                            "schemaVersion": "2.0.0",
                            "timestamp": "2026-10-01T00:00:00Z",
                            "selections": [
                                {
                                    "namespace": "ssvc",
                                    "key": "E",
                                    "version": "1.1.0",
                                    "values": [{"key": "P"}],
                                }
                            ],
                        }
                    },
                    "products": ["WIDGET-1"],
                }
            ],
            "product_status": {"known_affected": ["WIDGET-1"]},
        }
    ]
    return data


def section(data: dict[str, JsonValue], *path: str) -> dict[str, JsonValue]:
    """Return the object at *path* inside *data*, for a test to edit in place."""
    node: JsonValue = data
    for key in path:
        assert isinstance(node, dict), f"{key!r} is not inside an object"
        node = node[key]
    assert isinstance(node, dict), f"{path!r} is not an object"
    return node
