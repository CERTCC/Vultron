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
"""Which spec groups specify a demo scenario, and the two registers (DEMOCI-11-010).

DEMOCI-11-010 requires every demo scenario that has a spec group to sit in
exactly one of two registers — the scenario registry if it is built, the
planned-scenario register in ``notes/demo-future-ideas.md`` if it is specified
but not yet built.  Checking that partition needs a mechanical answer to "which
spec groups specify a demo scenario", and the two obvious answers are both
wrong:

- **A title substring.** Matching ``"Scenario"`` in a group title also selects
  ``Scenario Coverage`` (DEMOMA-04), ``Shared Scenario Harness`` (DEMOMA-23),
  ``Causal Gating and Scenario Narratives`` (DEMOMA-22) and ``In-Process Fuzz
  Simulation Scenario`` (DEMOMA-18), none of which specifies a demo scenario.
- **"A group some per-scenario DEMOMA-16 requirement refines."**  That selects
  only DEMOMA-24 and DEMOMA-25; DEMOMA-20 (``rcv-embargo``) and DEMOMA-21
  (``rcvv-embargo``) have no DEMOMA-16 requirement at all, so this rule drops
  half the planned set and the partition check passes vacuously over it.

**The rule is MS-13-003's marker**, which already exists and already means
exactly this: a spec group describing a demo scenario workflow MUST carry
``trigger: {type: scenario_start, value: <name>}``, and SR-02-018 fixes
``value`` as the scenario's name.  Nothing enforced MS-13-003, so half the
scenario groups were missing it; :func:`scenario_spec_groups` is the selector
and :func:`partition_problems` is what makes the omission fail.

The marker is a *declaration*, not an inference, which is the property the two
rejected rules lack: a new scenario group is selected because its author said
so, not because its title happened to read a certain way.

Requirements: ``specs/demo-ci.yaml`` DEMOCI-11-007, DEMOCI-11-010;
``specs/meta-specifications.yaml`` MS-13-003.  Design: ADR-0098.
Guidance: ``notes/demo-scenario-registry.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from vultron.demo.scenario.registry import (
    ScenarioSpec,
    discover_scenarios,
    is_scenario_name,
)
from vultron.metadata.base import repo_root
from vultron.metadata.markdown_tables import iter_tables
from vultron.metadata.specs.registry import SpecRegistry, load_registry
from vultron.metadata.specs.schema import TriggerType

#: The note holding the planned-scenario register.
PLANNED_REGISTER = "notes/demo-future-ideas.md"

#: Heading of the register's table.  The register is located by heading rather
#: than by "the first table with a Scenario column", because that file holds
#: several other scenario-adjacent tables — deprecated scripts, cross-cutting
#: variations — and picking the wrong one would report the whole planned set as
#: missing.
PLANNED_REGISTER_HEADING = "Planned scenario register"

#: Column headers the register must carry.  DEMOCI-11-010 requires a planned
#: entry to name its tracking issue and its spec IDs, so both are columns rather
#: than prose: a column can be empty and detected, a sentence cannot.
PLANNED_COLUMNS = ("Scenario", "Tracking issue", "Spec IDs")

#: ``#1234`` — a tracking issue reference in the register's Issue cell.
_ISSUE_RE = re.compile(r"#(\d+)")

#: A spec ID as the corpus spells them: a group (``DEMOMA-20``) or a
#: requirement (``DEMOMA-16-014``).  Exported because ``prose_checks`` reads spec
#: IDs out of a table cell with the same grammar, and two copies of an ID pattern
#: is exactly the duplication CS-22-001 forbids.
SPEC_ID_RE = re.compile(r"\b([A-Z][A-Z0-9]*(?:-\d+)+)\b")

#: The phrase that marks a DEMOMA-16 requirement as being about *one
#: scenario's* required event types, as opposed to the universal list
#: (DEMOMA-16-001), the spec-to-test sync rule (DEMOMA-16-008), or the FCVCV
#: event-*count* requirements (DEMOMA-16-012, -013).  Selecting by what the
#: statement says is required rather than convenient: DEMOCI-11-007 warns that
#: the per-scenario requirements are not a contiguous ID range, and they are
#: not — -008 sits inside the span and -014/-015 sit outside it.
_EXPECTED_LIST_PHRASE = "expected-event-types list"

#: ``the FVCV-handoff scenario`` — how every per-scenario DEMOMA-16 requirement
#: names its subject.  Case-insensitive against the registry's ``name``, which
#: is what both registers spell, so no ``label`` column is needed anywhere to
#: resolve the mapping.
_SCENARIO_MENTION_RE = re.compile(
    r"\bthe\s+([A-Za-z0-9][A-Za-z0-9-]*)\s+scenario\b", re.IGNORECASE
)

#: Group whose requirements are the per-scenario event-type lists.
_EVENT_TYPE_GROUP = "DEMOMA-16"


@dataclass(frozen=True, slots=True)
class PlannedScenario:
    """One row of the planned-scenario register.

    Attributes:
        name: Scenario name in the registry's grammar (``rcv-embargo``).
        issues: Tracking issue numbers named by the row.
        spec_ids: Spec group or requirement IDs named by the row.
    """

    name: str
    issues: tuple[str, ...]
    spec_ids: tuple[str, ...]


def scenario_spec_groups(
    registry: SpecRegistry | None = None,
) -> dict[str, str]:
    """Return ``{scenario name: group id}`` for every marked scenario group.

    A group is a scenario group iff it carries MS-13-003's
    ``trigger: {type: scenario_start, value: <name>}``.

    Raises:
        ValueError: If a marker's value is not a valid scenario name, or if two
            groups claim the same scenario. Both are declaration errors that
            would otherwise make the partition check quietly wrong — a
            malformed name can match neither register, and a duplicate would
            let one group's omission hide behind another's presence.
    """
    resolved = (
        registry if registry is not None else load_registry(_specs_dir())
    )
    groups: dict[str, str] = {}
    for group_id, group in sorted(resolved.all_groups.items()):
        trigger = group.trigger
        if trigger is None or trigger.type is not TriggerType.SCENARIO_START:
            continue
        name = trigger.value
        if not is_scenario_name(name):
            raise ValueError(
                f"{group_id} carries a scenario_start trigger whose value "
                f"{name!r} is not a valid scenario name (SR-02-018). Expected "
                "the registry's grammar: lowercase alphanumerics separated by "
                "single hyphens, e.g. 'fvcv-handoff'."
            )
        if name in groups:
            raise ValueError(
                f"scenario {name!r} is claimed by two spec groups: "
                f"{groups[name]} and {group_id}. One scenario has one "
                "specifying group (MS-13-003)."
            )
        groups[name] = group_id
    return groups


def per_scenario_event_type_requirements(
    registry: SpecRegistry | None = None,
) -> dict[str, tuple[str, ...]]:
    """Return ``{scenario name: DEMOMA-16 requirement ids}``, lowercased names.

    A DEMOMA-16 requirement is per-scenario when its statement both mentions
    :data:`_EXPECTED_LIST_PHRASE` and names exactly one scenario. That pair of
    conditions is what separates the per-scenario requirements from those that
    are not:

    - DEMOMA-16-001 enumerates the universal types and names no scenario;
    - DEMOMA-16-008 is the spec-to-test sync rule and names no scenario;
    - DEMOMA-16-012 and -013 name FCVCV but are about *event counts* in the
      case-actor log, not about an expected-event-types list.

    Names are returned as spelled by the registry (lowercase), so the result
    keys directly against :func:`discover_scenarios` and the planned register.
    """
    resolved = (
        registry if registry is not None else load_registry(_specs_dir())
    )
    found: dict[str, list[str]] = {}
    for spec_id, spec in sorted(resolved.all_specs.items()):
        if not spec_id.startswith(f"{_EVENT_TYPE_GROUP}-"):
            continue
        if _EXPECTED_LIST_PHRASE not in spec.statement:
            continue
        mentioned = {
            match.group(1).lower()
            for match in _SCENARIO_MENTION_RE.finditer(spec.statement)
        }
        if len(mentioned) != 1:
            continue
        found.setdefault(mentioned.pop(), []).append(spec_id)
    return {name: tuple(ids) for name, ids in sorted(found.items())}


def planned_scenarios(root: Path | None = None) -> tuple[PlannedScenario, ...]:
    """Parse the planned-scenario register in ``notes/demo-future-ideas.md``.

    Raises:
        ValueError: If the register's heading or its required columns are
            absent. A parser that returned an empty tuple instead would report
            every planned scenario as missing from both registers, which reads
            as a content problem when it is a structural one.
    """
    base = root or repo_root()
    text = (base / PLANNED_REGISTER).read_text(encoding="utf-8")
    matches = [
        table
        for table in iter_tables(text)
        if table.heading == PLANNED_REGISTER_HEADING
    ]
    if not matches:
        raise ValueError(
            f"{PLANNED_REGISTER} has no table under a "
            f"'{PLANNED_REGISTER_HEADING}' heading. DEMOCI-11-010 requires the "
            "planned-scenario register to live there; the heading is how this "
            "check finds it among the file's other tables."
        )
    if len(matches) > 1:
        raise ValueError(
            f"{PLANNED_REGISTER} has {len(matches)} tables under "
            f"'{PLANNED_REGISTER_HEADING}'. The register is one table, or a "
            "scenario can sit in the second copy and satisfy neither check."
        )
    table = matches[0]
    missing = [
        column for column in PLANNED_COLUMNS if column not in table.columns
    ]
    if missing:
        raise ValueError(
            f"{PLANNED_REGISTER} planned-scenario register is missing the "
            f"{missing} column(s); DEMOCI-11-010 requires the scenario name, "
            "its tracking issue and its spec IDs each in their own column."
        )

    names = table.column("Scenario")
    issues = table.column("Tracking issue")
    spec_ids = table.column("Spec IDs")
    return tuple(
        PlannedScenario(
            name=name.strip().strip("`"),
            issues=tuple(_ISSUE_RE.findall(issue)),
            spec_ids=tuple(SPEC_ID_RE.findall(ids)),
        )
        for name, issue, ids in zip(names, issues, spec_ids)
    )


def partition_problems(
    root: Path | None = None,
    registry: SpecRegistry | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> list[str]:
    """Return every way the two registers fail to partition the spec'd scenarios.

    Checked in **both** directions, which is the whole point. Registry-to-prose
    alone reports agreement while ignoring DEMOMA-16-014 (``fcvd``) and
    DEMOMA-16-015 (``vc``) — scenarios *correctly* absent from the registry.
    That is the same blind spot that let a ``vc`` row sit in a table of
    available demos with a spec group, a tracking issue and no implementation
    (ADR-0098).

    DEMOCI-11-010 constrains only scenarios that *have* a spec group, so this
    function cannot see a registered scenario with no group at all — that is
    ``test_every_registered_scenario_is_named_by_a_spec_group``'s job, and it is
    a separate check for exactly that reason (ISSUE-3495). The reverse direction
    is covered here and admits no exception: a planned entry with no spec group is
    a row nothing specifies.

    Args:
        root: Where the **planned register** is read from. It does *not* locate
            the spec corpus: pass *registry* for that. The two are deliberately
            separable so a test can point a fixture register at the real spec
            groups, which is what every negative test here does.
        registry: Spec corpus to select scenario groups from. Defaults to the
            repository's own ``specs/``.
        specs: Registered scenarios. Defaults to the discovered registry.
    """
    resolved_specs = discover_scenarios() if specs is None else specs
    groups = scenario_spec_groups(registry)
    registered = {spec.name for spec in resolved_specs}
    planned = planned_scenarios(root)
    planned_names = [entry.name for entry in planned]

    problems: list[str] = []

    duplicates = sorted(
        {name for name in planned_names if planned_names.count(name) > 1}
    )
    for name in duplicates:
        problems.append(
            f"{name!r} appears more than once in the planned-scenario "
            f"register in {PLANNED_REGISTER}."
        )
    planned_set = set(planned_names)

    for name, group_id in sorted(groups.items()):
        in_registry = name in registered
        in_planned = name in planned_set
        if in_registry and in_planned:
            problems.append(
                f"{name!r} ({group_id}) is in both registers: it is registered "
                f"by its demo module and also listed as planned in "
                f"{PLANNED_REGISTER}. Registration means built — remove the "
                "planned row (DEMOCI-11-010)."
            )
        elif not in_registry and not in_planned:
            problems.append(
                f"{name!r} ({group_id}) is in neither register. Add its "
                f"@scenario decorator if it is built, or a row in the "
                f"{PLANNED_REGISTER} planned-scenario register if it is not "
                "(DEMOCI-11-010)."
            )

    for name in sorted(planned_set - set(groups)):
        problems.append(
            f"{name!r} is in the {PLANNED_REGISTER} planned-scenario register "
            "but no spec group specifies it. Add "
            "'trigger: {type: scenario_start, value: " + name + "}' to its "
            "group (MS-13-003), or remove the row — a planned scenario is "
            "declared by its spec group plus the register, not the register "
            "alone (DEMOCI-11-010)."
        )

    for entry in planned:
        if not entry.issues:
            problems.append(
                f"planned scenario {entry.name!r} names no tracking issue; "
                "DEMOCI-11-010 requires one."
            )
        if not entry.spec_ids:
            problems.append(
                f"planned scenario {entry.name!r} names no spec IDs; "
                "DEMOCI-11-010 requires them."
            )

    return problems


def _specs_dir() -> Path:
    """Return the repository's ``specs/`` directory."""
    return repo_root() / "specs"


__all__ = [
    "PLANNED_COLUMNS",
    "PLANNED_REGISTER",
    "PLANNED_REGISTER_HEADING",
    "SPEC_ID_RE",
    "PlannedScenario",
    "partition_problems",
    "per_scenario_event_type_requirements",
    "planned_scenarios",
    "scenario_spec_groups",
]
