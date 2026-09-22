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
"""Scan scenario-table consumers for prose that copies the table (DEMOCI-11-008).

The prose half of the checked-consumer split; :mod:`.prose_tables` is the table
half and :mod:`.prose_checks` aggregates both.  Two scans, both over the same
declared consumer list:

- :func:`restated_counts` — no consumer may restate the registered scenario
  count, because the table is the count (DEMOCI-11-008, MS-16-001);
- :func:`stray_scenario_includes` — no file outside the MkDocs tree may source a
  scenario table with ``{% include-markdown %}``, because the plugin expands only
  at mkdocs build time and the directive renders literally everywhere else
  (DEMOCI-11-006).

Requirements: ``specs/demo-ci.yaml`` DEMOCI-11-006, DEMOCI-11-008;
``specs/meta-specifications.yaml`` MS-16-001, MS-16-002.
Guidance: ``notes/demo-scenario-registry.md``, ``notes/specs-vs-adrs.md``.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.metadata.markdown_tables import iter_sections

#: Files that consume a scenario table and so must not restate its row count
#: (DEMOCI-11-008).  Includes the generated artifacts: a count in the prose
#: *around* a generated table is a copy the generator does not maintain.
#:
#: Every path MUST exist — see :func:`restated_counts` for why a missing one is
#: an error rather than a skip.
SCENARIO_TABLE_CONSUMERS: tuple[str, ...] = (
    ".github/workflows/demo-integration.yml",
    "docs/topics/scenarios/index.md",
    "notes/README.md",
    "notes/demo-ci-diagnostics.md",
    "notes/demo-ci-invariants.md",
    "notes/demo-ci-scenario-coverage.md",
    "notes/demo-future-ideas.md",
    "notes/demo-scenario-authoring.md",
    "notes/demo-scenario-registry.md",
    "test/ci/README-case-log-ratchet.md",
    "vultron/demo/scenario/README.md",
)

#: Deliberately *not* a consumer: ``notes/specs-vs-adrs.md`` tabulates
#: restated-count phrasings as counter-examples for MS-16-001, so its "bad"
#: column must keep them. A check cannot tell a counter-example from the thing it
#: warns against, and rewriting that table would delete the guidance. The
#: exemption is recorded in that note itself, not only here, so whoever edits the
#: counter-examples learns why they survive.
EXEMPT_CONSUMERS: tuple[str, ...] = ("notes/specs-vs-adrs.md",)

_COUNT_WORDS = (
    "two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    "fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty"
)

#: Words that make a following ``scenario`` a different grammatical object, so a
#: number in front of them is not counting scenarios. Two groups:
#:
#: - articles and prepositions — ``#2018 as a scenario-specific type``;
#: - copulas — ``Invariant 8 is scenario-local`` predicates something *about* the
#:   number 8; it does not count eight scenarios.
_NOT_A_MODIFIER = r"(?!(?:as|of|in|and|or|to|a|an|the|is|are|was|were)\s)"

#: A restated scenario count: ``9 demo scenarios``, ``nine scenarios``,
#: ``4-scenario minimum set``.
#:
#: Four guards keep it off text that is not a count. Every one of them was added
#: because a real line in these files tripped the version without it:
#:
#: - ``(?<![#\\w-])`` — the count must not continue an identifier. ``#2018`` is an
#:   issue reference and ``DEMOMA-16`` / ``ADR-0098`` are spec and decision IDs,
#:   all of which these files cite constantly and often right next to the word
#:   "scenario" (``DEMOMA-16 scenario event types`` would otherwise report
#:   ``16 scenario``).
#: - at most two modifier words, none of them a stopword — see
#:   :data:`_NOT_A_MODIFIER`.
#: - the hyphenated form is a separate alternative rather than ``[-\\s]``, so
#:   ``FCVCV 5-Party Scenario`` (which counts *parties*) does not match while
#:   ``full 9-scenario suite`` does.
#: - ``one`` is absent from :data:`_COUNT_WORDS`: ``one scenario per matrix
#:   entry`` is a rate, not an inventory.
#:
#: Whitespace is ``\\s+`` throughout because these counts wrap: one live
#: restatement read ``all eight multi-actor\\n  scenarios``, and a line-at-a-time
#: scan misses it.
_COUNT_RE = re.compile(
    rf"(?<![#\w-])(?:\d+|{_COUNT_WORDS})"
    rf"(?:\s+(?:{_NOT_A_MODIFIER}[a-z][a-z-]*\s+){{0,2}}scenarios?|-scenario)\b",
    re.IGNORECASE,
)

#: A heading that makes its section a record of past states.  A change-history
#: section legitimately says "updated from 8 to 9 scenarios": that sentence is
#: about what the workflow used to hold, and rewriting it would destroy the
#: record rather than remove a copy. The exemption is keyed on the heading so it
#: is visible to whoever writes the sentence, not buried in this module.
#:
#: Fully parenthesised: ``\\b(?:change )?history|changelog\\b`` binds each ``\\b``
#: to one outer alternative only, which exempts ``Prechangelog`` and any heading
#: merely containing "history" as a substring.
_HISTORY_HEADING_RE = re.compile(
    r"\b(?:(?:change )?history|changelog)\b", re.IGNORECASE
)

#: ``{% include-markdown "path" %}`` with its target captured.  A directive with
#: no quoted target is prose *about* the mechanism — ``AGENTS.md`` cites one that
#: way — and cannot source anything, so it is not a use of it.
_INCLUDE_RE = re.compile(r"\{%-?\s*include-markdown\s+[\"']([^\"']+)[\"']")

#: Directory names never searched for stray include directives.
_SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "site",
        "__pycache__",
        ".mypy_cache",
    }
)


def _exempt_scopes(text: str) -> list[tuple[tuple[int, str], ...]]:
    """Return the line groups a count scan should read, history sections removed.

    The exemption **inherits to subsections**. ``iter_sections`` is flat, so a
    ``#### PR log`` nested inside ``### Change history`` is its own section with
    its own heading, which does not match — and the lines the exemption exists to
    protect would be reported. A section is therefore exempt when its own heading
    matches *or* when it is deeper than the nearest enclosing exempt heading and
    no shallower non-exempt heading has intervened.
    """
    scopes: list[tuple[tuple[int, str], ...]] = []
    exempt_at: int | None = None
    for section in iter_sections(text):
        if exempt_at is not None and section.level <= exempt_at:
            # Left the exempt section: a heading at or above its level closes it.
            exempt_at = None
        if _HISTORY_HEADING_RE.search(section.heading):
            exempt_at = section.level
            continue
        if exempt_at is not None:
            continue
        scopes.append(section.lines)
    return scopes


def restated_counts(root: Path | None = None) -> list[str]:
    """Return every prose restatement of the scenario count (DEMOCI-11-008).

    Restatements inside a change-history section are exempt; see
    :func:`_exempt_scopes` for why that is a heading-level rule that inherits.

    **The exemption applies to markdown only.** In a non-markdown consumer a
    leading ``#`` opens a comment, not a heading, so sectioning
    ``demo-integration.yml`` would turn each of its ~50 comment lines into a
    "heading" — and any comment containing the word "history" would then silence
    the check for every line below it. Those files are scanned whole instead, and
    the exemption is simply unavailable in them.

    Raises:
        FileNotFoundError: If a declared consumer does not exist. Skipping a
            missing path would drop it from the check silently, so a rename would
            remove a file from DEMOCI-11-008 coverage with every test still
            green — the opposite of a ratchet.
    """
    base = root or repo_root()
    findings: list[str] = []
    for path in SCENARIO_TABLE_CONSUMERS:
        target = base / path
        if not target.is_file():
            raise FileNotFoundError(
                f"{path} is declared in SCENARIO_TABLE_CONSUMERS but does not "
                "exist, so it is silently outside the no-restated-count check. "
                "Update the tuple in "
                "vultron/metadata/demo_scenarios/prose_counts.py if the file "
                "moved (DEMOCI-11-008)."
            )
        text = target.read_text(encoding="utf-8")
        if target.suffix == ".md":
            scopes = _exempt_scopes(text)
        else:
            scopes = [tuple(enumerate(text.splitlines(), start=1))]
        for lines in scopes:
            findings.extend(_counts_in(path, lines))
    return findings


def _counts_in(path: str, lines: tuple[tuple[int, str], ...]) -> list[str]:
    """Return count restatements in *lines*, each tagged with its line number.

    Matched against the joined text rather than line by line because these
    counts wrap; the line number is then recovered from the match offset.
    """
    body = "\n".join(line for _number, line in lines)
    numbers = [number for number, _line in lines]
    bounds: list[int] = []
    cursor = 0
    for _number, line in lines:
        bounds.append(cursor)
        cursor += len(line) + 1
    findings: list[str] = []
    for match in _COUNT_RE.finditer(body):
        index = bisect_right(bounds, match.start()) - 1
        line_number = numbers[index] if 0 <= index < len(numbers) else 0
        findings.append(
            f"{path}:{line_number}: "
            f"{match.group(0)!r} restates the scenario count; the table is "
            "the count (DEMOCI-11-008)."
        )
    return findings


def stray_scenario_includes(root: Path | None = None) -> list[str]:
    """Return ``{% include-markdown %}`` directives that cannot work.

    DEMOCI-11-006 forbids sourcing a scenario table with an include directive
    outside the MkDocs tree: the plugin expands only at mkdocs build time, so
    the directive renders as literal text to every reader of ``notes/``,
    ``test/ci/`` or a package README.

    Scoped to directives whose target names a scenario, because the qualifier is
    load-bearing rather than decorative — ``AGENTS.md`` cites
    ``{% include-markdown %}`` in prose, with no target, and must not trip this.
    """
    base = root or repo_root()
    findings: list[str] = []
    docs = base / "docs"
    for path in sorted(base.rglob("*.md")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.is_relative_to(docs):
            continue
        text = path.read_text(encoding="utf-8")
        for match in _INCLUDE_RE.finditer(text):
            target = match.group(1)
            if "scenario" not in target.lower():
                continue
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                f"{path.relative_to(base)}:{line}: "
                f'{{% include-markdown "{target}" %}} sources a scenario '
                "table outside the MkDocs tree, where it renders literally. "
                "Generate the table between markers instead, or check it in "
                "place (DEMOCI-11-006)."
            )
    return findings


__all__ = [
    "EXEMPT_CONSUMERS",
    "SCENARIO_TABLE_CONSUMERS",
    "restated_counts",
    "stray_scenario_includes",
]
