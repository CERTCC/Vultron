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
"""Compact term index of ``docs/reference/glossary.md`` (``glossary-index``).

The glossary is ~80 KB; reading it whole at the start of every agent session
costs ~20k tokens, most of it definitions the task never touches. The
``orient-agent`` skill reads this index instead: every term, the aliases to
avoid for it (the naming guard), and each section's line range, so
``deepen-context`` can read only the sections a task needs.

Output, one line per ``##`` section::

    L11-21 Core CVD Concepts: Vulnerability; Report (not: Submission, notice)
    L409-469 Relationships (prose)
"""

from __future__ import annotations

import sys
from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.metadata.markdown_tables import (
    MarkdownSection,
    MarkdownTable,
    iter_sections,
    iter_tables,
)

GLOSSARY_PATH = Path("docs/reference/glossary.md")

#: Alias cells that mean "no aliases".
_EMPTY_ALIASES = frozenset({"", "—", "-", "–", "n/a", "N/A"})


def _strip_bold(cell: str) -> str:
    return cell.replace("**", "").strip()


def _term_entries(table: MarkdownTable) -> list[str]:
    """Return ``Term (not: aliases)`` entries for one table, in row order."""
    has_aliases = "Aliases to avoid" in table.columns
    aliases = (
        table.column("Aliases to avoid")
        if has_aliases
        else ("",) * len(table.rows)
    )
    entries = []
    for row, alias in zip(table.rows, aliases):
        if not row:
            continue
        term = _strip_bold(row[0])
        if alias.strip() not in _EMPTY_ALIASES:
            term = f"{term} (not: {alias.strip()})"
        entries.append(term)
    return entries


def _heading_lines(text: str) -> list[tuple[int, MarkdownSection]]:
    """Pair each section with the 1-based line number of its own heading.

    :func:`iter_sections` excludes the heading line from ``lines``, and a
    section with an empty body carries no line numbers at all — so the heading
    line cannot be read off ``lines[0]``. Sections tile the document in order,
    so walk them with a cursor instead: ``0`` for the headingless preamble.
    """
    paired: list[tuple[int, MarkdownSection]] = []
    cursor = 0
    for section in iter_sections(text):
        heading = 0 if section.level == 0 else cursor + 1
        paired.append((heading, section))
        cursor = section.lines[-1][0] if section.lines else heading
    return paired


def render_index(text: str) -> str:
    """Render the term index for glossary markdown *text*."""
    sections = [(n, s) for n, s in _heading_lines(text) if s.level == 2]
    tables = sorted(iter_tables(text), key=lambda t: t.line)

    total = len(text.splitlines())
    lines = []
    for i, (start, section) in enumerate(sections):
        end = sections[i + 1][0] - 1 if i + 1 < len(sections) else total
        span = f"L{start}-{end}"
        # Match tables by line range, not by heading text: two sections can
        # share a title, and grouping on the title gave each the other's terms.
        entries = [
            entry
            for table in tables
            if start <= table.line <= end
            for entry in _term_entries(table)
        ]
        if entries:
            lines.append(f"{span} {section.heading}: {'; '.join(entries)}")
        else:
            lines.append(f"{span} {section.heading} (prose)")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Print the glossary term index (``glossary-index`` entry point)."""
    path = repo_root() / GLOSSARY_PATH
    sys.stdout.write(
        f"# {GLOSSARY_PATH} — term index (read sections by line range)\n"
    )
    sys.stdout.write(render_index(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
