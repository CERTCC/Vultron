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


def minimal_csaf_document() -> dict[str, Any]:
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
