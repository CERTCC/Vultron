"""Ratchet: every scenario harness lists the five universal semantic types.

DEMOMA-16-001 declares five semantic types — ``validate_report``,
``add_participant_status_to_participant``, ``close_case``,
``add_note_to_case``, and ``engage_case`` — that MUST appear in the
authoritative case-actor log of *every* multi-actor demo scenario.  Each
scenario harness implements that requirement as the leading entries of its
``_XXX_EXPECTED_SEMANTIC_TYPES`` constant.

DEMOMA-16-018 requires the spec requirement and the test constants to change
in the same PR.  Nothing enforced that structurally: ``engage_case`` was added
to ``test_rvcv_handoff_invariants.py`` alone (PR #2018) without amending the
spec, leaving an engage-case regression silent in every other scenario
(CONCERN-2243, ISSUE-2266).  These tests close that gap by checking, without
running any demo, that

1. every harness named by the CI matrix carries the universal block, and
2. DEMOMA-16-001 still enumerates exactly the same five types.

Scenario→harness mapping comes from ``.github/demo-scenarios.json``.  That file
is now a *generated* projection of the scenario registry in
``vultron/demo/scenario/registry/`` (ADR-0098, DEMOCI-11-004) rather than the
declaration point it once was, but it is still the right thing to read here:
it is what the CI matrix actually expands, so a harness missing from it is a
harness CI never runs.  Do not add a second list of harness files here.
"""

from __future__ import annotations

import functools
import importlib
import json
import re
from pathlib import Path
from types import ModuleType

import pytest
from _pytest.mark.structures import ParameterSet

from vultron.metadata.specs.registry import load_registry

_REPO_ROOT = Path(__file__).parents[3]
_CI_SCENARIOS_JSON = _REPO_ROOT / ".github" / "demo-scenarios.json"
_SPECS_DIR = _REPO_ROOT / "specs"

#: The DEMOMA-16-001 universal semantic types, in the order the harnesses list
#: them.  Amending this tuple requires amending DEMOMA-16-001 in the same PR
#: (DEMOMA-16-018) — ``test_demoma_16_001_enumerates_the_universal_types``
#: fails otherwise.
_UNIVERSAL_SEMANTIC_TYPES = (
    "validate_report",
    "add_participant_status_to_participant",
    "close_case",
    "add_note_to_case",
    "engage_case",
)

_EXPECTED_CONST_RE = re.compile(r"^_[A-Z0-9_]+_EXPECTED_SEMANTIC_TYPES$")


def _harness_modules() -> list[ParameterSet]:
    """One param per CI-matrix scenario: (demo name, harness module name)."""
    entries = json.loads(_CI_SCENARIOS_JSON.read_text())
    return [
        pytest.param(
            entry["demo"],
            entry["test_file"].removesuffix(".py").replace("/", "."),
            id=entry["demo"],
        )
        for entry in entries
    ]


def _expected_semantic_types_constant(
    module: ModuleType,
) -> tuple[str, list[str]]:
    """Return the harness's single expected-semantic-types constant name + values.

    Values are the ``semanticType`` strings in declaration order.  Entries may be
    ``pytest.param(...)`` (the convention in every harness) or a bare
    string, which pytest also accepts.
    """
    names = [n for n in vars(module) if _EXPECTED_CONST_RE.match(n)]
    assert len(names) == 1, (
        f"{module.__name__} must declare exactly one "
        f"_XXX_EXPECTED_SEMANTIC_TYPES constant, found {sorted(names)}"
    )
    name = names[0]
    semantic_types = []
    for entry in getattr(module, name):
        value = entry if isinstance(entry, str) else entry.values[0]
        assert isinstance(value, str), (
            f"{name} entry {entry!r} does not wrap a semanticType string"
        )
        semantic_types.append(value)
    return name, semantic_types


@pytest.mark.parametrize(("demo", "module_name"), _harness_modules())
def test_harness_lists_universal_semantic_types_once(
    demo: str, module_name: str
) -> None:
    """Each harness's universal block is the five DEMOMA-16-001 types.

    The universal types lead the constant, in DEMOMA-16-001 order, and none is
    repeated further down among the scenario-specific entries (AC-3 of
    ISSUE-2266): a duplicated presence check adds no coverage and hides which
    block owns the requirement.
    """
    module = importlib.import_module(module_name)
    const_name, semantic_types = _expected_semantic_types_constant(module)
    where = f"{const_name} ({demo})"

    assert (
        tuple(semantic_types[: len(_UNIVERSAL_SEMANTIC_TYPES)])
        == _UNIVERSAL_SEMANTIC_TYPES
    ), (
        f"{where} must open with the DEMOMA-16-001 universal block "
        f"{list(_UNIVERSAL_SEMANTIC_TYPES)}; got {semantic_types}"
    )

    for semantic_type in _UNIVERSAL_SEMANTIC_TYPES:
        assert semantic_types.count(semantic_type) == 1, (
            f"{where} lists {semantic_type!r} {semantic_types.count(semantic_type)} "
            "times; universal types belong in the universal block exactly once"
        )


#: The notes whose ``Scenario`` tables list every CI-matrix scenario by name.
_SCENARIO_TABLE_NOTES = (
    _REPO_ROOT / "notes" / "demo-ci-invariants.md",
    _REPO_ROOT / "notes" / "demo-ci-scenario-coverage.md",
)


def _scenario_tables(note: Path) -> list[set[str]]:
    """The scenario names in each table of *note* whose first header is ``Scenario``.

    A name is the row's first cell, lower-cased with spaces as hyphens, so the
    invariants note's ``RCV embargo`` reads as the matrix's ``rcv-embargo``.
    """
    tables: list[list[str]] = []
    current: list[str] = []
    for line in [*note.read_text().splitlines(), ""]:
        if line.startswith("|"):
            current.append(line)
        elif current:
            tables.append(current)
            current = []
    return [
        {
            row.split("|")[1].strip().lower().replace(" ", "-")
            for row in table[2:]
        }
        for table in tables
        if table[0].split("|")[1].strip() == "Scenario"
    ]


def _scenario_table_ids() -> list[ParameterSet]:
    """One param per (note, ``Scenario`` table) pair, so a failure names its table."""
    return [
        pytest.param(note, index, id=f"{note.name}-table-{index}")
        for note in _SCENARIO_TABLE_NOTES
        for index in range(len(_scenario_tables(note)))
    ]


@pytest.mark.parametrize(("demo", "module_name"), _harness_modules())
def test_each_ci_scenario_has_its_harness_and_notes_rows(
    demo: str, module_name: str
) -> None:
    """A CI-matrix scenario names a harness that exists and has its notes rows.

    The scenarios are enumerated by name in DEMOMA-16 and in the ``Scenario``
    tables of ``notes/demo-ci-invariants.md`` and
    ``notes/demo-ci-scenario-coverage.md``, so adding one means a row in each.
    Checked per scenario rather than as a pinned total, so two PRs that each
    add a scenario do not race on one number (``notes/testing-pitfalls.md``,
    #3984).
    """
    entry = next(
        e
        for e in json.loads(_CI_SCENARIOS_JSON.read_text())
        if e["demo"] == demo
    )
    assert (_REPO_ROOT / entry["test_file"]).is_file(), (
        f"CI matrix entry {demo!r} names a nonexistent harness file"
        f" {entry['test_file']} (module {module_name})"
    )
    for note in _SCENARIO_TABLE_NOTES:
        tables = _scenario_tables(note)
        assert tables, f"{note.name} has no table headed 'Scenario'"
        for index, names in enumerate(tables):
            assert demo in names, (
                f"{note.name} Scenario table {index} has no row for {demo!r};"
                " a new CI scenario needs a row in each scenario table"
            )


@pytest.mark.parametrize(("note", "index"), _scenario_table_ids())
def test_each_notes_scenario_row_is_a_ci_scenario(
    note: Path, index: int
) -> None:
    """Every row of a notes ``Scenario`` table names a CI-matrix scenario.

    The other direction of the check above: a scenario removed from the matrix
    must lose its rows, so the tables never describe a scenario CI no longer
    runs.
    """
    demos = {e["demo"] for e in json.loads(_CI_SCENARIOS_JSON.read_text())}
    stale = sorted(_scenario_tables(note)[index] - demos)
    assert not stale, (
        f"{note.name} Scenario table {index} lists {stale}, which are not in"
        " .github/demo-scenarios.json"
    )


@functools.cache
def _spec_ids() -> frozenset[str]:
    """Every requirement ID in the spec registry, read once for all params."""
    return frozenset(load_registry(_SPECS_DIR).all_specs)


@pytest.mark.spec_corpus
@pytest.mark.parametrize(("demo", "module_name"), _harness_modules())
def test_each_ci_scenario_names_its_demoma_16_requirement(
    demo: str, module_name: str
) -> None:
    """A CI scenario's invariants-note row cites a DEMOMA-16 requirement that exists.

    DEMOMA-16 holds one expected-semantic-types requirement per scenario, and
    the ``Spec`` column of ``notes/demo-ci-invariants.md`` names it, so a new
    scenario fails here until its requirement is written.
    """
    note = _SCENARIO_TABLE_NOTES[0]
    specs = [
        row.split("|")[2].strip()
        for row in note.read_text().splitlines()
        if row.startswith("|")
        and row.split("|")[1].strip().lower().replace(" ", "-") == demo
    ]
    assert len(specs) == 1, (
        f"{note.name} should have one row for {demo!r} ({module_name}),"
        f" found {len(specs)}"
    )
    assert re.fullmatch(r"DEMOMA-16-\d{3}", specs[0]), (
        f"{note.name} row for {demo!r} cites {specs[0]!r}, not a DEMOMA-16 ID"
    )
    assert specs[0] in _spec_ids(), (
        f"{note.name} row for {demo!r} cites {specs[0]}, which is not in specs/"
    )


@pytest.mark.spec_corpus
def test_demoma_16_001_enumerates_the_universal_types() -> None:
    """DEMOMA-16-001's statement names exactly the five universal types.

    Guards the spec side of DEMOMA-16-008: promoting or retiring a universal
    semantic type in the harnesses without amending DEMOMA-16-001 fails here.
    """
    statement = load_registry(_SPECS_DIR).get("DEMOMA-16-001").statement
    quoted = set(re.findall(r"`([a-z_]+)`", statement))
    assert quoted == set(_UNIVERSAL_SEMANTIC_TYPES), (
        "DEMOMA-16-001 must enumerate exactly the universal semantic types "
        f"{sorted(_UNIVERSAL_SEMANTIC_TYPES)}; its statement names "
        f"{sorted(quoted)}"
    )
