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
"""Ratchet the ``notes/`` scenario *tables* against their sources (DEMOCI-11-007).

The table half of the checked-consumer split; :mod:`.prose_counts` is the prose
half and :mod:`.prose_checks` aggregates both.  Split out because one module
holding both grew past the size CS-18-001 asks a multi-responsibility module to
stay under, and the two halves share nothing but the markdown reader.

**Why these tables are checked in place rather than column-generated.**  Only
their ``Scenario`` column is registry-derived, and a markdown column cannot be
spliced independently of the row it heads.  A generator would therefore have to
emit whole rows — including the hand-written cells it cannot know — so adding a
scenario would make it write a placeholder row and call the artifact
"generated".  DEMOCI-11-006 and DEMOCI-11-007 say *checked in place* for exactly
this case, and what a check costs relative to generation is one edit by the
author who knows the hand-written cells; what it buys is that the file never
contains a cell nobody wrote.

Requirements: ``specs/demo-ci.yaml`` DEMOCI-11-006, DEMOCI-11-007;
``specs/meta-specifications.yaml`` MS-16-002.
Guidance: ``notes/demo-scenario-registry.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios
from vultron.metadata.base import repo_root
from vultron.metadata.demo_scenarios.event_types import (
    additional_event_types,
    harness_event_types,
)
from vultron.metadata.demo_scenarios.scenario_groups import (
    SPEC_ID_RE,
    per_scenario_event_type_requirements,
)
from vultron.metadata.markdown_tables import MarkdownTable, iter_tables
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
        event_type_column: Header of a column naming the event types the
            scenario requires *beyond* the universal block, or ``None``. Derived
            from the harness's ``_XXX_EXPECTED_EVENT_TYPES`` constant
            (ISSUE-3505), which is the live answer Invariant 5 asserts against.
            Parenthesised annotations in the cell (``(≥3)``, ``(none)``) are
            multiplicity commentary, not event types, and are ignored.
        tick_columns: When true, every column but ``Scenario`` is an event-type
            name and a non-empty cell asserts that the scenario exercises it —
            the coverage-matrix shape. Ratcheted against the same harness
            constants (ISSUE-3505); these ticks were the file's last unratcheted
            mirror.
    """

    path: str
    heading: str
    spelling: Literal["name", "label"]
    spec_column: str | None = None
    pr_set_column: str | None = None
    event_type_column: str | None = None
    tick_columns: bool = False


#: Every ``notes/`` table whose rows are the scenarios.  Adding a table here is
#: what puts it under the check.
#:
#: The tuple is not the authority on *which* tables exist — it cannot be, since a
#: hand-maintained list reintroduces the silent omission the registry exists to
#: remove (DEMOCI-11-002).  ``undeclared_scenario_tables()`` closes that by
#: scanning the consumer files for any table whose first column is scenario
#: names, so a new one fails rather than being quietly unratcheted.
SCENARIO_TABLES: tuple[ScenarioTable, ...] = (
    ScenarioTable(
        path="notes/demo-ci-scenario-coverage.md",
        heading="Coverage Matrix",
        spelling=_BY_NAME,
        tick_columns=True,
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
        event_type_column="Additional required",
    ),
)


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


def undeclared_scenario_tables(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> list[str]:
    """Return scenario tables in the consumer files that no entry declares.

    :data:`SCENARIO_TABLES` is hand-maintained, so on its own it has the defect
    DEMOCI-11-002's rationale names: a table absent from it is unratcheted and
    nothing says so.  This is the ratchet over the list itself — a table is
    "a scenario table" when its first column holds two or more registered
    scenario names, which is a property of the content rather than of anybody
    remembering to add a row here.

    Generated tables are excluded by construction: they live in the files
    ``sync.py`` writes, not in the two ``notes/`` files scanned here.
    """
    base = root or repo_root()
    resolved = discover_scenarios() if specs is None else specs
    known = {spec.name for spec in resolved} | {
        spec.label for spec in resolved
    }
    declared = {(table.path, table.heading) for table in SCENARIO_TABLES}
    scanned = sorted({table.path for table in SCENARIO_TABLES})

    findings: list[str] = []
    for path in scanned:
        text = (base / path).read_text(encoding="utf-8")
        for parsed in iter_tables(text):
            first = [
                cell.strip().strip("`")
                for cell in parsed.column(parsed.columns[0])
            ]
            if len([cell for cell in first if cell in known]) < 2:
                continue
            if (path, parsed.heading) in declared:
                continue
            findings.append(
                f"{path}:{parsed.line} table under {parsed.heading!r} lists "
                "scenarios but no SCENARIO_TABLES entry declares it, so it is "
                "unratcheted. Add one in "
                "vultron/metadata/demo_scenarios/prose_tables.py "
                "(DEMOCI-11-002, DEMOCI-11-007)."
            )
    return findings


def scenario_table_problems(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
    registry: SpecRegistry | None = None,
) -> list[str]:
    """Return every disagreement between a ``notes/`` scenario table and the source.

    Properties checked per table:

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
      derivable even though the rest of that cell is not;
    - where it carries an event-type column, each row names exactly the event
      types that scenario's harness constant requires beyond the universal set
      (ISSUE-3505).
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
            problems.extend(
                _spec_column_problems(table, parsed, resolved, per_scenario)
            )

        if table.pr_set_column is not None:
            problems.extend(_pr_set_column_problems(table, parsed, resolved))

        if table.event_type_column is not None:
            problems.extend(
                _additional_column_problems(table, parsed, resolved, base)
            )

        if table.tick_columns:
            problems.extend(_tick_problems(table, parsed, resolved, base))
    return problems


def _spec_column_problems(
    table: ScenarioTable,
    parsed: MarkdownTable,
    resolved: tuple[ScenarioSpec, ...],
    per_scenario: dict[str, tuple[str, ...]],
) -> list[str]:
    """Return rows whose ``Spec`` cell disagrees with the spec corpus."""
    column = table.spec_column or ""
    problems: list[str] = []
    for spec, cell in zip(resolved, parsed.column(column)):
        named = set(SPEC_ID_RE.findall(cell))
        wanted = set(per_scenario.get(spec.name, ()))
        if named != wanted:
            problems.append(
                f"{table.path}:{parsed.line} row {spec.label!r} names "
                f"{sorted(named)} in its {column} column; the spec corpus has "
                f"{sorted(wanted)} for that scenario (DEMOCI-11-007)."
            )
    return problems


def _pr_set_column_problems(
    table: ScenarioTable,
    parsed: MarkdownTable,
    resolved: tuple[ScenarioSpec, ...],
) -> list[str]:
    """Return rows whose PR-set mark disagrees with the ``in_pr_set`` field."""
    column = table.pr_set_column or ""
    problems: list[str] = []
    for spec, cell in zip(resolved, parsed.column(column)):
        marked = cell.strip().startswith(_IN_PR_SET_MARK)
        if marked != spec.in_pr_set:
            problems.append(
                f"{table.path}:{parsed.line} row {spec.name!r} marks "
                f"{column} as "
                f"{'a member' if marked else 'not a member'}; the "
                f"@scenario decorator sets in_pr_set={spec.in_pr_set} "
                "(MS-16-002, DEMOCI-11-007)."
            )
    return problems


def _cell_event_types(cell: str) -> frozenset[str]:
    """Return the event-type names *cell* lists.

    Multiplicity annotations are dropped: the column's job is to say *which*
    types are required, and ``(≥3)`` / ``(none)`` are prose about how many
    times — a separate fact, owned by the scenario-specific count tests
    described in ``notes/demo-ci-invariants.md``.
    """
    return frozenset(
        token
        for token in (
            raw.strip().strip("`") for raw in cell.replace(",", " ").split()
        )
        if token and not token.startswith("(")
    )


def _additional_column_problems(
    table: ScenarioTable,
    parsed: MarkdownTable,
    resolved: tuple[ScenarioSpec, ...],
    root: Path,
) -> list[str]:
    """Return rows whose ``Additional required`` cell disagrees with the harness."""
    column = table.event_type_column or ""
    problems: list[str] = []
    for spec, cell in zip(resolved, parsed.column(column)):
        harness = harness_event_types(spec, root)
        if harness is None:
            # No harness file. For a *registered* scenario that is a missing
            # derived path, which DEMOCI-11-003 already reports via
            # ``sync.missing_derived_paths`` — re-checking it here would be the
            # CS-22-001 duplication this module exists to avoid. The skip is
            # therefore safe only while both run from the same command; see
            # ``sync.main``, which extends one problem list with both.
            continue
        wanted = additional_event_types(harness)
        named = _cell_event_types(cell)
        if named != wanted:
            problems.append(
                f"{table.path}:{parsed.line} row {spec.label!r} names "
                f"{sorted(named)} in its {column} column; {spec.name}'s "
                f"harness constant requires {sorted(wanted)} beyond the "
                "universal block (MS-16-002, DEMOCI-11-007)."
            )
    return problems


def _tick_problems(
    table: ScenarioTable,
    parsed: MarkdownTable,
    resolved: tuple[ScenarioSpec, ...],
    root: Path,
) -> list[str]:
    """Return tick-matrix cells that disagree with the harness constants.

    Each ✓ asserts that a named event type appears in a named scenario's
    expected list, which is exactly what the harness constant declares — so the
    matrix is checkable, and MS-16-002 requires it to be checked.  A stale tick
    makes a scenario look like it exercises a phase it does not, which is an
    argument for shrinking the PR validation set on false evidence
    (ISSUE-3505).
    """
    columns = [name for name in parsed.columns if name != "Scenario"]
    problems: list[str] = []

    unknown = [name for name in columns if not name.islower()]
    if unknown:
        problems.append(
            f"{table.path}:{parsed.line} tick matrix has non-event-type "
            f"columns {unknown}; every column but 'Scenario' must be an "
            "event_type name for the harness ratchet to read it "
            "(DEMOCI-11-007)."
        )
        return problems

    for spec, row in zip(resolved, parsed.rows):
        harness = harness_event_types(spec, root)
        if harness is None:
            # No harness file. For a *registered* scenario that is a missing
            # derived path, which DEMOCI-11-003 already reports via
            # ``sync.missing_derived_paths`` — re-checking it here would be the
            # CS-22-001 duplication this module exists to avoid. The skip is
            # therefore safe only while both run from the same command; see
            # ``sync.main``, which extends one problem list with both.
            continue
        expected = frozenset(harness)
        cells = dict(zip(parsed.columns, row))
        for name in columns:
            ticked = bool(cells.get(name, "").strip())
            if ticked != (name in expected):
                problems.append(
                    f"{table.path}:{parsed.line} row {spec.name!r} marks "
                    f"{name!r} as "
                    f"{'exercised' if ticked else 'not exercised'}; "
                    f"{spec.name}'s harness constant says otherwise "
                    "(MS-16-002, DEMOCI-11-007, ISSUE-3505)."
                )
    return problems


__all__ = [
    "SCENARIO_TABLES",
    "ScenarioTable",
    "scenario_table_problems",
    "undeclared_scenario_tables",
]
