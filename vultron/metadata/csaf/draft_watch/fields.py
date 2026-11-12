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
"""The CSAF fields this codebase reads, and which a change touches (CSAF-05-007)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from vultron.metadata.csaf.draft_watch.schemas import (
    SchemaSet,
    UnresolvedReferenceError,
)


@dataclass(frozen=True)
class ReadField:
    """A CSAF field this codebase reads, as a document path, and why."""

    path: str
    specs: tuple[str, ...]


#: The CSAF fields this codebase reads, with the requirements that read them.
#: ``[]`` steps into the items of an array. A test checks that each one
#: resolves in the pinned schema, so a path that drifts from it fails.
READ_FIELDS: tuple[ReadField, ...] = (
    ReadField("$schema", ("CSAF-01-003",)),
    ReadField("document.csaf_version", ("CSAF-01-003",)),
    ReadField("document.category", ("CSAF-02-001", "CSAF-04-009")),
    ReadField("document.title", ("CSAF-03-007", "CSAF-04-010")),
    ReadField("document.notes[].category", ("CSAF-03-007", "CSAF-04-010")),
    ReadField("document.notes[].text", ("CSAF-03-007", "CSAF-04-010")),
    ReadField("document.references[]", ("CSAF-03-009",)),
    ReadField("document.distribution.tlp.label", ("CSAF-04-004",)),
    ReadField("document.acknowledgments[]", ("CSAF-04-004",)),
    ReadField("document.involvement.entities[].name", ("CSAF-04-004",)),
    ReadField(
        "vulnerabilities[].disclosure_date",
        (
            "CSAF-03-001",
            "CSAF-03-002",
            "CSAF-03-003",
            "CSAF-04-006",
            "CSAF-04-010",
        ),
    ),
    ReadField(
        "vulnerabilities[].first_known_exploitation_dates[]",
        ("CSAF-03-005", "CSAF-04-006"),
    ),
    ReadField(
        "vulnerabilities[].metrics[].content.ssvc_v2",
        ("CSAF-03-004", "CSAF-04-006"),
    ),
    ReadField("vulnerabilities[].cve", ("CSAF-03-008",)),
    ReadField("vulnerabilities[].ids[]", ("CSAF-03-008",)),
    ReadField("vulnerabilities[].title", ("CSAF-03-008",)),
    ReadField("vulnerabilities[].notes[].category", ("CSAF-03-008",)),
    ReadField("vulnerabilities[].notes[].text", ("CSAF-03-008",)),
    ReadField("vulnerabilities[].notes[].title", ("CSAF-03-008",)),
    ReadField("vulnerabilities[].notes[].audience", ("CSAF-03-008",)),
    ReadField("vulnerabilities[].references[]", ("CSAF-03-008",)),
    ReadField(
        "vulnerabilities[].product_status.known_affected[]", ("CSAF-04-007",)
    ),
    ReadField("product_tree.branches[].category", ("CSAF-04-007",)),
    ReadField("product_tree.branches[].name", ("CSAF-04-007",)),
    ReadField("product_tree.branches[].product.product_id", ("CSAF-04-007",)),
)


@dataclass(frozen=True)
class AffectedField:
    """A read field the upstream change touches, and how."""

    field: ReadField
    how: str


def affected_fields(
    baseline: SchemaSet,
    upstream: SchemaSet,
    read_fields: Sequence[ReadField] = READ_FIELDS,
) -> list[AffectedField]:
    """Return each of *read_fields* whose schema differs between the two sides.

    Raises:
        ValueError: a read field does not resolve in *baseline*, the pinned
            schema, so :data:`READ_FIELDS` has drifted from it.
    """
    affected: list[AffectedField] = []
    for read in read_fields:
        located = baseline.locate(read.path)
        if located is None:
            raise ValueError(
                f"{read.path} is not a field of the pinned CSAF schema"
            )
        pinned = baseline.expand(*located)
        try:
            found = upstream.locate(read.path)
            if found is None:
                affected.append(AffectedField(read, "is gone upstream"))
            elif upstream.expand(*found) != pinned:
                affected.append(AffectedField(read, "changed"))
        except UnresolvedReferenceError as exc:
            affected.append(
                AffectedField(
                    read,
                    f"cannot be read upstream: `{exc}` does not resolve there",
                )
            )
    return affected
