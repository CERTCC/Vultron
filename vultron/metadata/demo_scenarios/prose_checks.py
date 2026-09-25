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
is the generate half.  This module is the entry point to the check half, and
holds the two checks that belong to neither sub-module plus the aggregate the
CLI calls:

- the ``mkdocs.yml`` nav, whose labels are hand-written (DEMOCI-11-007);
- the per-scenario DEMOMA-16 requirements, one per registered scenario
  (DEMOCI-11-007);
- :func:`consistency_problems`, which composes those with
  :mod:`.prose_tables` (the ``notes/`` scenario tables), :mod:`.prose_counts`
  (restated counts and stray include directives), :mod:`.scenario_groups` (the
  two-register partition) and the DEMOCI-06 spec enumerations.

The table and prose halves live in sibling modules because one module holding
both grew past the size CS-18-001 asks a multi-responsibility module to stay
under, and they share nothing but the markdown reader.

Requirements: ``specs/demo-ci.yaml`` DEMOCI-06-002, DEMOCI-06-003,
DEMOCI-11-006 through DEMOCI-11-010.
Guidance: ``notes/demo-scenario-registry.md``.
"""

from __future__ import annotations

from pathlib import Path

from vultron.demo.scenario.registry import (
    ScenarioSpec,
    discover_scenarios,
    is_scenario_name,
)
from vultron.metadata.base import nav_paths, repo_root
from vultron.metadata.demo_scenarios.prose_counts import (
    SCENARIO_TABLE_CONSUMERS,
    restated_counts,
    stray_scenario_includes,
)
from vultron.metadata.demo_scenarios.prose_tables import (
    SCENARIO_TABLES,
    ScenarioTable,
    scenario_table_problems,
    undeclared_scenario_tables,
)
from vultron.metadata.demo_scenarios.scenario_groups import (
    partition_problems,
    per_scenario_event_type_requirements,
)
from vultron.metadata.specs.registry import SpecRegistry, load_registry

#: Spec statements that enumerate a scenario set in prose, with the predicate
#: selecting which registered scenarios each must name.  DEMOCI-11-007 keeps
#: these as prose rather than rewriting them into pointers, so they are checked.
_SCENARIO_SET_STATEMENTS: tuple[tuple[str, str], ...] = (
    ("DEMOCI-06-002", "in_pr_set"),
    ("DEMOCI-06-003", "all"),
)


def missing_narrative_nav_entries(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> list[str]:
    """Return registered scenarios whose narrative page is absent from the nav.

    Completeness only: the nav's labels are hand-written short forms (``FV``,
    ``FCCV-handoff``) that the registry's ``label`` does not always match, so
    the nav is checked for omission rather than regenerated (DEMOCI-11-007).
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


def scenario_set_statement_problems(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
    registry: SpecRegistry | None = None,
) -> list[str]:
    """Return DEMOCI-06 statements that no longer name the right scenario set.

    Both statements enumerate scenarios in prose, so both drift when the registry
    changes: DEMOCI-06-002 names the PR subset and DEMOCI-06-003 the whole suite.

    Scenario names are picked out of the statement with the registry's own
    grammar via :func:`is_scenario_name`, which is what makes this robust against
    the statements' other backticked spans — ``demo-integration.yml`` carries a
    dot and ``push: branches: ["main"]`` carries spaces and brackets, and the
    grammar admits neither.

    Previously these two lived only as pytest assertions. That left
    ``demo-scenarios --check`` — the pre-commit hook — reporting less than it
    claimed to, so a stale DEMOCI-06-003 reached CI before anything complained.
    """
    base = root or repo_root()
    resolved = discover_scenarios() if specs is None else specs
    loaded = load_registry(base / "specs") if registry is None else registry

    problems: list[str] = []
    for spec_id, selector in _SCENARIO_SET_STATEMENTS:
        statement = loaded.get(spec_id).statement
        named = {
            token
            for token in _backticked(statement)
            if is_scenario_name(token)
        }
        expected = {
            spec.name
            for spec in resolved
            if selector == "all" or spec.in_pr_set
        }
        if named != expected:
            problems.append(
                f"{spec_id} names scenarios {sorted(named)}; the registry has "
                f"{sorted(expected)}. Amend the statement in the same PR as the "
                "registry change (DEMOCI-11-007)."
            )
    return problems


def _backticked(text: str) -> list[str]:
    """Return every backtick-delimited span in *text*."""
    spans: list[str] = []
    parts = text.split("`")
    # Odd indices are the delimited spans: "a `b` c" splits to ['a ', 'b', ' c'].
    for index in range(1, len(parts), 2):
        spans.append(parts[index])
    return spans


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
    # A structural failure — a renamed table heading or column, a missing
    # register heading, a malformed marker, a consumer path that moved — is
    # raised by design so a test sees the cause. From the CLI it is one more
    # problem line: a pre-commit hook that answers with a traceback tells the
    # developer less than the exception's own message does.
    #
    # KeyError is caught alongside ValueError because MarkdownTable.column()
    # raises it deliberately: a renamed *column* is as much a structural failure
    # as a renamed heading, and catching only ValueError let it reach the hook as
    # a traceback while this comment claimed otherwise. FileNotFoundError covers
    # a declared consumer that moved.
    for check in (
        lambda: scenario_set_statement_problems(base, resolved, registry),
        lambda: undeclared_scenario_tables(base, resolved),
        lambda: scenario_table_problems(base, resolved, registry),
        lambda: restated_counts(base),
        lambda: stray_scenario_includes(base),
        lambda: partition_problems(base, registry, resolved),
    ):
        try:
            problems.extend(check())
        except (ValueError, KeyError, FileNotFoundError) as error:
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
    "scenario_set_statement_problems",
    "scenario_table_problems",
    "stray_scenario_includes",
    "undeclared_scenario_tables",
]
