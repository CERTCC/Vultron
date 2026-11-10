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

"""Whether a Reporter may attach the CSAF document it submits (CSAF-04-009).

The submit-report trigger is a strict sender: it attaches a CSAF document only
when a receiver will take it as the sender's statement, so a Reporter learns of
a fault before the report is sent rather than never (CSAF-02-007).  A receiver
is lenient and never refuses a report over its attachment (CSAF-02-006); this
check is the sending side's alone.
"""

from vultron.core.models.report_claims import (
    MAX_CSAF_CONTENT_CHARS,
    SubmittedCsafDocument,
)
from vultron.core.services.report_case_inputs import CSAF_VULNERABILITY_REPORT
from vultron.errors import Violation

#: The request field every fault of a submitted CSAF document is about.
CSAF_DOCUMENT_FIELD = "csaf_document"


def submitted_csaf_violations(
    submission: SubmittedCsafDocument,
) -> list[Violation]:
    """Every fault that keeps *submission* off a report; empty when none.

    A fault is each CSAF 2.1 schema error, at its path in the document
    (CSAF-02-007), a ``document.category`` other than
    ``csaf_vulnerability_report``, the one profile a receiver fills a case
    from (CSAF-02-001, CSAF-04-009), and content longer than a receiver
    reads.  Every one is reported, not only the first (EH-07-001).
    """
    violations: list[Violation] = []
    content = submission.attachment.content or ""
    if len(content) > MAX_CSAF_CONTENT_CHARS:
        violations.append(
            Violation(
                f"the document holds {len(content)} characters, more than"
                f" the {MAX_CSAF_CONTENT_CHARS} a receiver reads as CSAF",
                dimensions=(CSAF_DOCUMENT_FIELD,),
            )
        )
    violations.extend(
        Violation(
            f"{error.path}: {error.message} (CSAF 2.1 schema, CSAF-02-007)",
            dimensions=(CSAF_DOCUMENT_FIELD,),
        )
        for error in submission.reading.schema_errors
    )
    category = submission.reading.claims.document_category
    if category != CSAF_VULNERABILITY_REPORT:
        stated = (
            "states no document.category"
            if category is None
            else f"has document.category {category!r}"
        )
        violations.append(
            Violation(
                f"the document {stated}; submit-report attaches only a"
                f" {CSAF_VULNERABILITY_REPORT!r} (CSAF-04-009)",
                dimensions=(CSAF_DOCUMENT_FIELD,),
            )
        )
    return violations


__all__ = ["CSAF_DOCUMENT_FIELD", "submitted_csaf_violations"]
