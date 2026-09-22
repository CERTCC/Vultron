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
"""Check the hand-written scenario prose against the registry (DEMOCI-11-007).

ADR-0098 routes each consumer of the scenario set by what it is: generate what
is derivable, check what is prose.  :mod:`vultron.metadata.demo_scenarios.sync`
is the generate half.  This module is the check half, covering the four
consumers that cannot hold a generated table:

- the ``mkdocs.yml`` nav, whose labels are hand-written (DEMOCI-11-007);
- the ``notes/`` scenario tables, whose rows interleave hand-written columns the
  registry does not hold;
- every consumer's prose, which must not restate the scenario count
  (DEMOCI-11-008);
- any file outside the MkDocs tree, which must not source a scenario table with
  ``{% include-markdown %}`` (DEMOCI-11-006).

**Why the ``notes/`` tables are checked in place rather than column-generated.**
Only their ``Scenario`` column is registry-derived, and a markdown column cannot
be spliced independently of the row it heads.  A generator would therefore have
to emit whole rows — including the hand-written cells it cannot know — so adding
a scenario would make it write a placeholder row and call the artifact
"generated".  DEMOCI-11-006 and DEMOCI-11-007 say *checked in place* for exactly
this case, and what a check costs relative to generation is one edit by the
author who knows the hand-written cells; what it buys is that the file never
contains a cell nobody wrote.

Requirements: ``specs/demo-ci.yaml`` DEMOCI-11-006 through DEMOCI-11-008.
Guidance: ``notes/demo-scenario-registry.md``.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios
from vultron.metadata.base import nav_paths, repo_root
from vultron.metadata.demo_scenarios.scenario_groups import (
    SPEC_ID_RE,
    partition_problems,
    per_scenario_event_type_requirements,
)
from vultron.metadata.markdown_tables import (
    MarkdownTable,
    iter_sections,
    iter_tables,
)
from vultron.metadata.specs.registry import SpecRegistry

#: Spelling of a scenario in a table's ``Scenario`` column.  Two consumers,
#: two spellings: the coverage matrix keys rows by sub-command ``name`` while
#: the required-event-types table uses the display ``label``.  Declared per
#: table rather than guessed, because guessing wrong reports every row as
#: misspelled.
_BY_NAME: Literal["name"] = "name"
_BY_LABEL: Literal["label"] = "label"

#: How a table cell marks PR-set membership. Shared with the renderer's
#: ``_IN_SET``, but not imported from it: that one is the *generated* tables'
#: mark, and coupling a hand-written table's spelling to a generated one would
#: make a renderer change silently reclassify every row here.
_IN_PR_SET_MARK = "✓"


@dataclass(frozen=True, slots=True)
class ScenarioTable:
    """A hand-written table whose row set is the registry's (DEMOCI-11-007).

    Attributes:
        path: Repository-relative path of the containing file.
        heading: Heading text the table sits under. The table is located by
            heading because these files hold several other tables whose rows are
            event types, dimensions or RM transitions rather than scenarios.
        spelling: :data:`_BY_NAME` or :data:`_BY_LABEL`.
        spec_column: Header of a column holding the row's per-scenario DEMOMA-16
            requirement IDs, or ``None``. Derived from the **spec corpus**, not
            the registry — ``ScenarioSpec`` carries no spec IDs; each DEMOMA-16
            statement names its own scenario.
        pr_set_column: Header of a column whose cell marks PR-set membership
            with a leading ``✓``, or ``None``. Derived from ``in_pr_set``
            (MS-16-002): the membership half of that cell drifts independently
            of the decorator, and a test can falsify it, so it is ratcheted
            rather than left as prose. The rest of the cell stays hand-written —
            *which* scenario covers a non-member is a coverage judgement the
            registry does not hold.
    """

    path: str
    heading: str
    spelling: Literal["name", "label"]
    spec_column: str | None = None
    pr_set_column: str | None = None


#: Every ``notes/`` table whose rows are the scenarios.  Adding a table here is
#: what puts it under the check; a scenario table absent from this tuple is
#: unratcheted, which is the state DEMOCI-11-007 exists to end.
SCENARIO_TABLES: tuple[ScenarioTable, ...] = (
    ScenarioTable(
        path="notes/demo-ci-scenario-coverage.md",
        heading="Coverage Matrix",
        spelling=_BY_NAME,
    ),
    ScenarioTable(
        path="notes/demo-ci-scenario-coverage.md",
        heading="Minimum PR Validation Set (DEMOCI-06-002)",
        spelling=_BY_NAME,
        pr_set_column="Covered by minimum set",
    ),
    ScenarioTable(
        path="notes/demo-ci-invariants.md",
        heading="Scenario required event types",
        spelling=_BY_LABEL,
        spec_column="Spec",
    ),
)

#: Files that consume a scenario table and so must not restate its row count
#: (DEMOCI-11-008).  Includes the generated artifacts: a count in the prose
#: *around* a generated table is a copy the generator does not maintain.
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
#: warns against, and rewriting that table would delete the guidance.

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


def missing_narrative_nav_entries(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> list[str]:
    """Return registered scenarios whose narrative page is absent from the nav.

    Completeness only: the nav's labels are hand-written short forms (``FV``,
    ``FCCV-handoff``) that the registry's ``label`` does not always match, so
    the nav is checked for omission rather than regenerated — the same treatment
    ``missing_nav_entries()`` gives the ADR pages (DEMOCI-11-007).
    """
    base = root or repo_root()
    resolved = discover_scenarios() if specs is None else specs
    navved = nav_paths(base)
    docs_prefix = "docs/"
    return [
        f"{spec.name}: {spec.narrative_path}"
        for spec in resolved
        if spec.narrative_path.removeprefix(docs_prefix) not in navved
    ]


def missing_event_type_requirements(
    specs: tuple[ScenarioSpec, ...] | None = None,
    registry: SpecRegistry | None = None,
) -> list[str]:
    """Return registered scenarios with no per-scenario DEMOMA-16 requirement.

    Each such requirement is a scenario's citable spec ID for its expected event
    types, so a registered scenario without one has no normative statement of
    what its invariant harness must observe.
    """
    resolved = discover_scenarios() if specs is None else specs
    per_scenario = per_scenario_event_type_requirements(registry)
    return [spec.name for spec in resolved if spec.name not in per_scenario]


def _table_for(table: ScenarioTable, root: Path) -> MarkdownTable:
    """Return the parsed markdown table *table* declares.

    Raises:
        ValueError: If the heading is absent or carries more than one table.
            Returning nothing instead would report every scenario as missing
            from a table that is merely somewhere else.
    """
    text = (root / table.path).read_text(encoding="utf-8")
    found = [
        parsed
        for parsed in iter_tables(text)
        if parsed.heading == table.heading
    ]
    if len(found) != 1:
        raise ValueError(
            f"{table.path}: expected exactly one table under "
            f"{table.heading!r}, found {len(found)}. This check locates the "
            "table by heading; a renamed heading or a second table there makes "
            "it unfindable (DEMOCI-11-007)."
        )
    return found[0]


def scenario_table_problems(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
    registry: SpecRegistry | None = None,
) -> list[str]:
    """Return every disagreement between a ``notes/`` scenario table and the source.

    Two properties are checked per table:

    - the ``Scenario`` column is exactly the registry's scenarios, in the
      registry's name order. Order is checked, not just membership, because name
      order is the canonical order for every consumer — a table that groups the
      PR set first makes position a second, unratcheted fact about the same
      rows;
    - where the table carries a ``Spec`` column, each row names exactly the
      per-scenario DEMOMA-16 requirements for that scenario, resolved from the
      spec corpus;
    - where it carries a PR-set column, the rows marked ``✓`` are exactly the
      ``in_pr_set`` scenarios. MS-16-002 requires a drift-prone fact to be
      derived or ratcheted rather than left as prose, and membership is
      derivable even though the rest of that cell is not.
    """
    base = root or repo_root()
    resolved = discover_scenarios() if specs is None else specs
    problems: list[str] = []
    per_scenario = per_scenario_event_type_requirements(registry)

    for table in SCENARIO_TABLES:
        parsed = _table_for(table, base)
        expected = tuple(
            spec.name if table.spelling == _BY_NAME else spec.label
            for spec in resolved
        )
        cleaned = tuple(
            cell.strip().strip("`") for cell in parsed.column("Scenario")
        )
        if cleaned != expected:
            problems.append(
                f"{table.path}:{parsed.line} table under {table.heading!r} "
                f"lists scenarios {list(cleaned)}; the registry has "
                f"{list(expected)} (name order, DEMOCI-11-007)."
            )
            continue

        if table.spec_column is not None:
            for spec, cell in zip(resolved, parsed.column(table.spec_column)):
                named = set(SPEC_ID_RE.findall(cell))
                wanted = set(per_scenario.get(spec.name, ()))
                if named != wanted:
                    problems.append(
                        f"{table.path}:{parsed.line} row {spec.label!r} names "
                        f"{sorted(named)} in its {table.spec_column} column; "
                        f"the spec corpus has {sorted(wanted)} for that "
                        "scenario (DEMOCI-11-007)."
                    )

        if table.pr_set_column is not None:
            for spec, cell in zip(
                resolved, parsed.column(table.pr_set_column)
            ):
                marked = cell.strip().startswith(_IN_PR_SET_MARK)
                if marked != spec.in_pr_set:
                    problems.append(
                        f"{table.path}:{parsed.line} row {spec.name!r} marks "
                        f"{table.pr_set_column} as "
                        f"{'a member' if marked else 'not a member'}; the "
                        f"@scenario decorator sets in_pr_set="
                        f"{spec.in_pr_set} (MS-16-002, DEMOCI-11-007)."
                    )
    return problems


def restated_counts(root: Path | None = None) -> list[str]:
    """Return every prose restatement of the scenario count (DEMOCI-11-008).

    Restatements inside a change-history section are exempt; see
    :data:`_HISTORY_HEADING_RE` for why that is a heading-level rule.

    **The exemption applies to markdown only.** In a non-markdown consumer a
    leading ``#`` opens a comment, not a heading, so sectioning
    ``demo-integration.yml`` would turn each of its ~50 comment lines into a
    "heading" — and any comment containing the word "history" would then silence
    the check for every line below it. Those files are scanned whole instead, and
    the exemption is simply unavailable in them.
    """
    base = root or repo_root()
    findings: list[str] = []
    for path in SCENARIO_TABLE_CONSUMERS:
        target = base / path
        if not target.is_file():
            continue
        text = target.read_text(encoding="utf-8")
        if target.suffix == ".md":
            scopes = [
                section.lines
                for section in iter_sections(text)
                if not _HISTORY_HEADING_RE.search(section.heading)
            ]
        else:
            scopes = [
                tuple(enumerate(text.splitlines(), start=1)),
            ]
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


def consistency_problems(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
    registry: SpecRegistry | None = None,
) -> list[str]:
    """Return every hand-written-prose disagreement, for the ``--check`` CLI.

    Aggregated here so ``uv run demo-scenarios --check`` — and therefore the
    ``demo-scenarios-sync`` pre-commit hook — reports the checked consumers
    alongside the generated ones. Generation and checking are the two halves of
    one split (ADR-0098); a developer who has to run a different command for
    each half will run only the one the hook names.
    """
    base = root or repo_root()
    resolved = discover_scenarios() if specs is None else specs
    problems: list[str] = []
    problems.extend(
        f"scenario narrative page is missing from the mkdocs nav — {entry} "
        "(DEMOCI-11-007)."
        for entry in missing_narrative_nav_entries(base, resolved)
    )
    problems.extend(
        f"registered scenario {name!r} has no per-scenario DEMOMA-16 "
        "requirement stating its expected event types (DEMOCI-11-007)."
        for name in missing_event_type_requirements(resolved, registry)
    )
    problems.extend(restated_counts(base))
    problems.extend(stray_scenario_includes(base))
    # A structural failure — a renamed table heading, a missing register
    # heading, a malformed marker — is a ValueError by design so a test sees the
    # cause. From the CLI it is one more problem line: a pre-commit hook that
    # answers with a traceback tells the developer less than the exception's own
    # message does. Both structural checks are wrapped, not just one, or a
    # renamed heading in `notes/` still reaches the hook as a traceback.
    for check in (
        lambda: scenario_table_problems(base, resolved, registry),
        lambda: partition_problems(base, registry, resolved),
    ):
        try:
            problems.extend(check())
        except ValueError as error:
            problems.append(str(error))
    return problems


__all__ = [
    "SCENARIO_TABLES",
    "SCENARIO_TABLE_CONSUMERS",
    "ScenarioTable",
    "consistency_problems",
    "missing_event_type_requirements",
    "missing_narrative_nav_entries",
    "restated_counts",
    "scenario_table_problems",
    "stray_scenario_includes",
]
