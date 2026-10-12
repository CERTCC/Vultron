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

"""No spec or note resolves its meaning by a decision record's detail number.

A citation such as "ADR-0099 detail 3" points into a record body, the only
place the detail number is defined, so the reader has to load that body to
know the rule. ADR-0127 takes record bodies out of routine agent context, and
MS-11-007 forbids the citation shape in ``specs/`` and ``notes/``: state the
rule in place, or cite the requirement that states it (ADR-0099's details now
live in ARCH-25).

The scan is whole-file text, so a citation folded across a line break, as YAML
and wrapped Markdown both do, is still found. Any "detail N" phrase is caught,
not only one that names its record, because a bare "(detail 2)" a sentence
after the record was named is the same citation. Decision records citing each
other are out of scope; ``docs/adr/`` is not scanned.
"""

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parents[2]

_SCAN_ROOTS = (_REPO_ROOT / "specs", _REPO_ROOT / "notes")

#: "detail 3", "details 7 and 8", "detail #4", "detail-6", case-insensitive,
#: with any whitespace (including a line break) between word and number. One
#: or two digits only, so "details 2026" (a year) is not a detail number.
DETAIL_CITATION_RE = re.compile(
    r"\bdetails?(?:\s+|-)#?\d{1,2}\b", re.IGNORECASE
)


def detail_citations(text: str) -> list[tuple[int, str]]:
    """Return ``(line, matched text)`` for each detail-number citation."""
    return [
        (text.count("\n", 0, m.start()) + 1, " ".join(m.group(0).split()))
        for m in DETAIL_CITATION_RE.finditer(text)
    ]


def _scanned_files() -> list[Path]:
    """Every file under the scan roots, whatever its suffix."""
    return sorted(
        path
        for root in _SCAN_ROOTS
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )


@pytest.mark.spec("MS-11-007")
def test_no_spec_or_note_names_a_numbered_decision_detail() -> None:
    files = _scanned_files()
    assert files, "the scan found no spec or notes files; the gate is vacuous"
    hits = [
        f"{path.relative_to(_REPO_ROOT)}:{line}: {match}"
        for path in files
        for line, match in detail_citations(path.read_text(encoding="utf-8"))
    ]
    assert not hits, (
        "Cite the requirement that states the rule, with the decision record "
        "as provenance only (MS-11-007):\n" + "\n".join(hits)
    )


@pytest.mark.parametrize(
    "text",
    [
        "an alias of the core class (ADR-0099 detail 3), not a subclass",
        "MUST NOT define a second actor class (ADR-0099 detail\n      3).",
        "on the core class (detail 2) and a bare state value (detail 5)",
        "**The rule (MV-11, ADR-0099 details 7 and 8 as amended).**",
        "| ADR-0099 Details 7–8 | The epic's closed children |",
        "the single detail-6 allow-list test",
        "ADR-0094 detail #2",
    ],
)
def test_detector_catches_each_citation_shape(text: str) -> None:
    assert detail_citations(text), text


@pytest.mark.parametrize(
    "text",
    [
        "an alias of the core class (ARCH-25-003), not a subclass",
        "implementation details are not part of the API",
        "exposes raw persistence details\n  to callers",
        "the details 2026 measurement",  # a year is not a detail number
    ],
)
def test_detector_passes_non_citations(text: str) -> None:
    assert not detail_citations(text), text
