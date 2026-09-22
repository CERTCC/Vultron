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
"""Section and table reader for the hand-written markdown the tooling checks.

Several ratchets need to read a markdown file structurally rather than by
substring: the diagnostic map in ``notes/demo-ci-diagnostics.md``, the scenario
tables in ``notes/demo-ci-invariants.md`` and
``notes/demo-ci-scenario-coverage.md``, and the planned-scenario register in
``notes/demo-future-ideas.md``.  Each of those previously grew its own regex,
which is the duplication CS-22-001 forbids, so the locating logic lives here
once.

Two primitives, because every caller needs one or both:

- :func:`iter_sections` partitions a document at ATX headings.  A check that
  must exempt one part of a file — a change-history section whose prose
  deliberately records a past count — needs the heading a line sits under, not
  just the line.
- :func:`iter_tables` yields each pipe table with the heading it sits under and
  the line it starts on, so a diagnostic can say *which* table disagreed.

Three hazards this module exists to absorb, the first two of which bit the
hand-rolled predecessors:

- **A ``#`` inside a fenced code block is not a heading.**  The regex in
  ``test_diagnostic_map_sync.py`` documented that it could not tell the
  difference and relied on its target section containing no fence.  Fences are
  tracked here, so callers inherit no such constraint.
- **A row is only a row if a delimiter row precedes it.**  Matching bare
  ``|``-delimited lines also matches prose that happens to contain pipes, and
  it silently accepts a table whose header was deleted.
- **A pipe table inside a fence is an example, not a table.**  A caller that
  requires exactly one table under a heading would otherwise break the moment
  someone documents that table's shape in a code block beneath it.
- **A fence may be indented.**  CommonMark allows 1–3 leading spaces, which is
  the normal form inside a list item and the form mkdocs-material admonitions
  require; a reader anchored at column 0 tracks none of them and so silently
  loses both guarantees above.  See :data:`_FENCE_RE`.
- **A delimiter row ends the table above it.**  Two tables with no blank line
  between them are two tables, not one with the second's header as a data row.
- **``\\|`` is a literal pipe, not a separator.**  Splitting on every pipe
  shifts every later column, so a ratchet fails while naming the wrong one.

A ``#`` in a *non-markdown* file opens a comment, not a heading, so do not
section one: see ``prose_checks.restated_counts`` for what that costs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: An ATX heading: one to six leading hashes, then whitespace, then the text.
_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.*?)\s*$")

#: A fence opener or closer. The info string after the ticks is ignored; only
#: the run length matters, because a longer run closes a shorter one.
#:
#: The 1–3 leading spaces CommonMark permits are matched deliberately, not
#: incidentally. An indented fence is the normal form inside a list item, and
#: this repository uses them in the files this module parses — ``MD046`` is
#: switched off in ``.markdownlint-cli2.yaml`` precisely because mkdocs-material
#: admonitions need indented blocks. Anchoring hard at column 0 would leave
#: every one of those fences untracked, so a ``#`` or a pipe table inside one
#: would be read as real content: the exact hazard the module docstring below
#: claims to absorb, failing silently in the most common case.
_FENCE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")

#: A table's delimiter row: ``|---|:---:|---|``. Its presence is what promotes
#: the line above it from prose-containing-pipes to a table header.
#:
#: One dash is enough, as CommonMark allows: requiring three would make a table
#: written ``|:--|--:|`` invisible to every caller, and invisible is the one
#: failure mode these checks exist to remove — a scenario table nothing parses is
#: a scenario table nothing ratchets.
_DELIMITER_RE = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+\s*$")

#: A cell separator: a pipe that is not escaped as ``\|``. GFM's escape is the
#: only way to put a literal pipe in a cell, so splitting on every pipe shifts
#: every column after the escape and makes :meth:`MarkdownTable.column` return a
#: neighbour's text — a ratchet failing while pointing at the wrong column.
_SEPARATOR_RE = re.compile(r"(?<!\\)\|")


def _is_row(line: str) -> bool:
    """Whether *line* is shaped like a pipe-table row.

    Both outer pipes are required. GFM makes them optional, so this is a
    deliberate narrowing of the dialect rather than an oversight: accepting
    bare ``a | b`` would make any prose line containing a pipe eligible to
    extend a table past its last row, which is a worse failure than rejecting
    a spelling nothing in this repository uses. The narrowing is *enforced*
    rather than assumed — ``MD055: leading_and_trailing`` in
    ``.markdownlint-cli2.yaml`` fails a table written without them, so a file
    that would parse wrong here cannot be committed.
    """
    stripped = line.strip()
    return (
        len(stripped) > 1
        and stripped.startswith("|")
        and stripped.endswith("|")
        and not stripped.endswith(r"\|")
    )


def split_row(line: str) -> tuple[str, ...]:
    """Split a pipe-table row into its stripped cell values.

    The outer pipes delimit rather than separate, so they are removed before
    splitting; otherwise every row gains a leading and trailing empty cell and
    the column count is two more than the table shows.

    ``\\|`` is a literal pipe, not a separator, and is unescaped in the value
    that is returned: a caller comparing a cell against a registry name wants
    the text the reader sees.
    """
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith(r"\|"):
        stripped = stripped[:-1]
    return tuple(
        cell.strip().replace(r"\|", "|")
        for cell in _SEPARATOR_RE.split(stripped)
    )


@dataclass(frozen=True, slots=True)
class MarkdownSection:
    """One ATX-heading section of a markdown document.

    Attributes:
        heading: The heading text, without its hashes. Empty for the preamble
            above the first heading (which is where front matter lives).
        level: Number of hashes, so 1 for ``#`` and 3 for ``###``. ``0`` for the
            preamble. Carried because a section-scoped rule is almost always
            meant to cover the subsections beneath it: an exemption keyed on
            ``### Change history`` that does not reach a ``#### PR log`` inside
            it fires on the very lines the exemption exists to protect.
        lines: ``(1-based line number, text)`` for every line in the body,
            excluding the heading line itself. Fenced code is *included*, so a
            caller scanning prose still sees it; callers that must not read
            fenced content consult :attr:`fenced`.
        fenced: Line numbers inside a fenced code block. Kept beside ``lines``
            rather than filtered out of it because the two callers disagree:
            :func:`iter_tables` must ignore a pipe table inside a fence, while a
            prose scan wants every line and its true number.
    """

    heading: str
    level: int
    lines: tuple[tuple[int, str], ...]
    fenced: frozenset[int]


@dataclass(frozen=True, slots=True)
class MarkdownTable:
    """One pipe table, with enough context to name it in a diagnostic.

    Attributes:
        heading: Heading text of the section the table sits in. Empty when the
            table precedes every heading.
        columns: Header cell values, stripped.
        rows: One tuple of stripped cell values per body row. Rows are *not*
            padded or truncated to ``columns``; a ragged table is a real defect
            and a caller that cares should say so rather than have it hidden.
        line: 1-based line number of the header row.
    """

    heading: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    line: int

    def column(self, name: str) -> tuple[str, ...]:
        """Return the values of the column headed *name*, in row order.

        Raises:
            KeyError: If no column carries that header. Raised rather than
                returning empty so that a renamed column fails loudly instead
                of reporting every row as missing.
        """
        try:
            index = self.columns.index(name)
        except ValueError:
            raise KeyError(
                f"table at line {self.line} under {self.heading!r} has no "
                f"{name!r} column; its columns are {list(self.columns)}"
            ) from None
        return tuple(
            row[index] if index < len(row) else "" for row in self.rows
        )


def iter_sections(text: str) -> tuple[MarkdownSection, ...]:
    """Partition *text* at ATX headings, ignoring hashes inside code fences.

    The preamble above the first heading is returned as a section with an empty
    heading, so no content is silently dropped: a check that scans "the whole
    document" gets the whole document.
    """
    sections: list[MarkdownSection] = []
    heading = ""
    level = 0
    body: list[tuple[int, str]] = []
    fenced: set[int] = set()
    fence: str | None = None

    for number, line in enumerate(text.splitlines(), start=1):
        opener = _FENCE_RE.match(line)
        run = opener.group("fence") if opener is not None else None
        if fence is None and run is not None:
            fence = run
            fenced.add(number)
        elif fence is not None:
            fenced.add(number)
            # A closing fence must use the same character and be at least as
            # long as the one it opened; a shorter run inside a longer block is
            # literal content, not a close.
            if (
                run is not None
                and len(run) >= len(fence)
                and run[0] == fence[0]
            ):
                fence = None

        match = None if fence is not None else _HEADING_RE.match(line)
        if match is None:
            body.append((number, line))
            continue

        sections.append(
            MarkdownSection(heading, level, tuple(body), frozenset(fenced))
        )
        heading = match.group("text")
        level = len(match.group("hashes"))
        body = []

    sections.append(
        MarkdownSection(heading, level, tuple(body), frozenset(fenced))
    )
    return tuple(sections)


def iter_tables(text: str) -> tuple[MarkdownTable, ...]:
    """Return every pipe table in *text*, in document order.

    Two guards, both load-bearing:

    - a table is recognised only where a delimiter row (``|---|---|``) follows a
      row-shaped line, so prose containing pipes is not a table;
    - fenced code is skipped, so a pipe table shown *as an example* inside a
      ``` block is not returned. Without this, a caller that expects exactly one
      table under a heading fails as soon as someone documents the table's shape
      beneath it.
    """
    tables: list[MarkdownTable] = []
    for section in iter_sections(text):
        lines = [
            (number, line)
            for number, line in section.lines
            if number not in section.fenced
        ]
        index = 0
        while index < len(lines):
            number, line = lines[index]
            following = lines[index + 1][1] if index + 1 < len(lines) else ""
            if not (_is_row(line) and _DELIMITER_RE.match(following.strip())):
                index += 1
                continue

            rows: list[tuple[str, ...]] = []
            cursor = index + 2
            while cursor < len(lines) and _is_row(lines[cursor][1]):
                # A delimiter row inside the body means the *previous* line was
                # the next table's header, not this table's last row. Without
                # this, two tables separated by no blank line merge into one
                # whose rows include the second table's header and delimiter —
                # which defeats every "exactly one table under this heading"
                # guard, because the caller is handed a single table.
                nxt = lines[cursor + 1][1] if cursor + 1 < len(lines) else ""
                if _DELIMITER_RE.match(nxt.strip()):
                    break
                rows.append(split_row(lines[cursor][1]))
                cursor += 1
            tables.append(
                MarkdownTable(
                    heading=section.heading,
                    columns=split_row(line),
                    rows=tuple(rows),
                    line=number,
                )
            )
            index = cursor
    return tuple(tables)


__all__ = [
    "MarkdownSection",
    "MarkdownTable",
    "iter_sections",
    "iter_tables",
    "split_row",
]
