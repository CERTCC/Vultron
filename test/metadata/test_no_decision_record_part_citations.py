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

"""No file resolves its meaning by a numbered part of a decision record.

A citation such as "ARCH-25-003 (ADR-0099)", "ADR-0009 Rule 1" or "ADR-0125,
decision part 7" points into a record body, the only place that number is
defined, so the reader has to load the body to know the rule. ADR-0127 takes
record bodies out of routine agent context, and MS-11-007 forbids the citation
shape in ``specs/``, ``notes/``, ``vultron/``, and ``test/``: state the rule
in place, or cite the requirement that states it, with the record as provenance
only.

One ``git grep`` call over the scan roots selects every line that holds a part
word and a number (or a part word at the end of a line, whose number is on the
next one), with a line of context either side. Python only joins each run of
adjacent lines and applies :data:`CITATION_RE`, so a citation folded across a
line break, as YAML and wrapped Markdown both do, is still found. Widening the
scan is one entry in :data:`SCAN_ROOTS`. This file itself is excluded from the
scan because its own detector-case strings and docstring contain citation shapes
by design.

A bare "detail N" is caught on its own, because "(detail 2)" a sentence after
the record was named is the same citation. The other part words in
:data:`_PART_WORDS`, and the section sign, are common in procedure text, so
they count only with a record ID within :data:`_NEARBY` characters of the same
sentence.
Decision records citing each other are out of scope; ``docs/adr/`` is not
scanned.
"""

import re
import subprocess
from collections import defaultdict
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parents[2]

#: Directories scanned, relative to the repository root.
SCAN_ROOTS: tuple[str, ...] = ("specs", "notes", "vultron", "test")

#: This file is excluded from the scan: its detector-case strings and
#: docstring contain citation shapes by design.
_EXCLUDE_SELF = (
    ":(exclude)test/metadata/test_no_decision_record_part_citations.py"
)

#: Whitespace (a line break included) or a hyphen, an optional "#", and one or
#: two digits, so "details 2026" (a year) is not a part number.
_NUMBER = r"(?:\s+|-)#?\d{1,2}\b"

#: The words naming a numbered part of a record body ("Rule 1", "invariant 4"),
#: each a pattern valid in both Python ``re`` and POSIX ERE.
_PART_WORDS: tuple[str, ...] = (
    "details?",
    "rules?",
    "steps?",
    "options?",
    "parts?",
    "invariants?",
    "sections?",
)
_PART_WORD = "|".join(_PART_WORDS)

#: A numbered part of a record body: a part word and a number, or "§ 3".
_PART = rf"(?:\b(?:{_PART_WORD}){_NUMBER}|§\s*\d{{1,2}}\b)"

_RECORD_ID = r"\bADR-\d{4}\b"

#: How far a record ID may sit from the part it names, without crossing a
#: sentence or clause end or another record ID.
_NEARBY = rf"(?:(?!{_RECORD_ID})[^.;]){{0,60}}?"

#: A citation of a numbered part of a decision record, case-insensitive.
CITATION_RE = re.compile(
    rf"\bdetails?{_NUMBER}"
    rf"|{_RECORD_ID}{_NEARBY}{_PART}"
    rf"|{_PART}{_NEARBY}{_RECORD_ID}",
    re.IGNORECASE,
)

#: The ``git grep`` line selector, POSIX ERE: a part word and a number, or a
#: part word ending the line. A superset of what :data:`CITATION_RE` matches on
#: the joined lines.
_CANDIDATE_ERE = (
    rf"\b({_PART_WORD})"
    r"([[:space:]]*-?[[:space:]]*#?[0-9]{1,2}\b|[[:space:]]*$)"
    r"|§([[:space:]]*[0-9]|[[:space:]]*$)"
)


def citations(text: str) -> list[tuple[int, str]]:
    """Return ``(line, matched text)`` for each record-part citation."""
    return [
        (text.count("\n", 0, m.start()) + 1, " ".join(m.group(0).split()))
        for m in CITATION_RE.finditer(text)
    ]


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args], cwd=_REPO_ROOT, capture_output=True, check=False
    )


def _scanned_file_count() -> int:
    """Tracked and untracked, non-ignored files under the scan roots."""
    listed = _git(
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        *SCAN_ROOTS,
    )
    assert listed.returncode == 0, listed.stderr.decode()
    return len([p for p in listed.stdout.split(b"\0") if p])


def _candidate_lines() -> dict[str, dict[int, str]]:
    """``{path: {line: text}}`` for every selected line and its context."""
    found = _git(
        "grep",
        "-z",
        "-n",
        "-I",
        "-i",
        "-E",
        "-C1",
        "--full-name",
        "--untracked",
        "-e",
        _CANDIDATE_ERE,
        "--",
        *SCAN_ROOTS,
        _EXCLUDE_SELF,
    )
    # Exit 1 is "no line selected"; anything else above 0 is a git failure.
    assert found.returncode in (0, 1), found.stderr.decode()
    lines: dict[str, dict[int, str]] = defaultdict(dict)
    for record in found.stdout.decode("utf-8").splitlines():
        if record == "--":
            continue
        path, line, text = record.split("\0", 2)
        lines[path][int(line)] = text
    return lines


def _adjacent_blocks(by_line: dict[int, str]) -> list[tuple[int, str]]:
    """``(first line, joined text)`` for each run of adjacent line numbers."""
    blocks: list[tuple[int, str]] = []
    block: list[int] = []
    for line_number in sorted(by_line):
        if block and line_number != block[-1] + 1:
            blocks.append((block[0], "\n".join(by_line[n] for n in block)))
            block = []
        block.append(line_number)
    if block:
        blocks.append((block[0], "\n".join(by_line[n] for n in block)))
    return blocks


def _hits() -> list[str]:
    return [
        f"{path}:{first + offset - 1}: {match}"
        for path, by_line in sorted(_candidate_lines().items())
        for first, text in _adjacent_blocks(by_line)
        for offset, match in citations(text)
    ]


@pytest.mark.spec("MS-11-007")
def test_no_file_names_a_numbered_decision_part() -> None:
    assert _scanned_file_count(), (
        f"the scan found no files under {SCAN_ROOTS}; the gate is vacuous"
    )
    hits = _hits()
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
        "the hexagonal architecture constraint (ADR-0009 Rule 1)",
        "Policy logic in the router violates ADR-0009 Rule 1 and makes",
        "for independent swapability (ADR-0027, Option 2).",
        "the old two-init-path back-fill (ADR-0041 Option 3).",
        "preserves the original ADR-0015 Option 4 behavior",
        "negotiation (ADR-0125, decision part 7). Committing it",
        "ADR-0118 reverses ADR-0065\n      part 5, which chose `DECLINED`.",
        "persisting it is ADR-0107 step 5",
        "Option 3 of ADR-0015",
        "entry accepts no further change (ADR-0122 invariant 4), so no",
        "it never saw the intermediate step (ADR-0108 § 3). Adjacency",
        "(ADR-0108 §1)",
        "as ADR-0108 section 3 explains",
    ],
)
def test_detector_catches_each_citation_shape(text: str) -> None:
    assert citations(text), text


@pytest.mark.parametrize(
    "text",
    [
        "an alias of the core class (ARCH-25-003), not a subclass",
        "the hexagonal architecture constraint (ARCH-01-001)",
        "implementation details are not part of the API",
        "exposes raw persistence details\n  to callers",
        "the details 2026 measurement",  # a year is not a part number
        "Step 3 of the case initialization sequence MUST",
        "`pr-execute` Phase 5 Step 2 resolves a `CONFLICTING` PR",
        "(path b, rule 1) a node whose",
        "the first fix (ADR-0021 § Clarification) had",
        "see §6 Report Management (RM) State Machine",
        "ADR-0085 broadened the post-close rule\n      beyond R*",
        # A sentence end separates the record from an unrelated step.
        "as ADR-0107 records. Step 2 then finds the record",
    ],
)
def test_detector_passes_non_citations(text: str) -> None:
    assert not citations(text), text


def test_adjacent_lines_join_into_one_block() -> None:
    by_line = {4: "a", 5: "b", 9: "c"}
    assert _adjacent_blocks(by_line) == [(4, "a\nb"), (9, "c")]


def test_a_folded_citation_reports_the_line_it_starts_on() -> None:
    text = "intro\nADR-0118 reverses ADR-0065\n  part 5, which chose X.\n"
    assert citations(text) == [(2, "ADR-0065 part 5")]
