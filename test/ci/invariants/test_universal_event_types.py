"""Ratchet: every scenario harness lists the five universal event types.

DEMOMA-16-001 declares five event types — ``validate_report``,
``add_participant_status_to_participant``, ``close_case``,
``add_note_to_case``, and ``engage_case`` — that MUST appear in the
authoritative case-actor log of *every* multi-actor demo scenario.  Each
scenario harness implements that requirement as the leading entries of its
``_XXX_EXPECTED_EVENT_TYPES`` constant.

DEMOMA-16-008 requires the spec requirement and the test constants to change
in the same PR.  Nothing enforced that structurally: ``engage_case`` was added
to ``test_fvcv_handoff_invariants.py`` alone (PR #2018) without amending the
spec, leaving an engage-case regression silent in the other eight scenarios
(CONCERN-2243, ISSUE-2266).  These tests close that gap by checking, without
running any demo, that

1. all nine harnesses named by the CI matrix carry the universal block, and
2. DEMOMA-16-001 still enumerates exactly the same five types.

Scenario→harness mapping comes from ``.github/demo-scenarios.json``, which is
the sole registry per ``notes/demo-ci-invariants.md``.  Do not add a second
list of harness files here.
"""

from __future__ import annotations

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

#: The DEMOMA-16-001 universal event types, in the order the harnesses list
#: them.  Amending this tuple requires amending DEMOMA-16-001 in the same PR
#: (DEMOMA-16-008) — ``test_demoma_16_001_enumerates_the_universal_types``
#: fails otherwise.
_UNIVERSAL_EVENT_TYPES = (
    "validate_report",
    "add_participant_status_to_participant",
    "close_case",
    "add_note_to_case",
    "engage_case",
)

_EXPECTED_CONST_RE = re.compile(r"^_[A-Z0-9_]+_EXPECTED_EVENT_TYPES$")


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


def _expected_event_types_constant(
    module: ModuleType,
) -> tuple[str, list[str]]:
    """Return the harness's single expected-event-types constant name + values.

    Values are the ``eventType`` strings in declaration order.  Entries may be
    ``pytest.param(...)`` (the convention in all nine harnesses) or a bare
    string, which pytest also accepts.
    """
    names = [n for n in vars(module) if _EXPECTED_CONST_RE.match(n)]
    assert len(names) == 1, (
        f"{module.__name__} must declare exactly one "
        f"_XXX_EXPECTED_EVENT_TYPES constant, found {sorted(names)}"
    )
    name = names[0]
    event_types = []
    for entry in getattr(module, name):
        value = entry if isinstance(entry, str) else entry.values[0]
        assert isinstance(
            value, str
        ), f"{name} entry {entry!r} does not wrap an eventType string"
        event_types.append(value)
    return name, event_types


@pytest.mark.parametrize(("demo", "module_name"), _harness_modules())
def test_harness_lists_universal_event_types_once(
    demo: str, module_name: str
) -> None:
    """Each harness's universal block is the five DEMOMA-16-001 types.

    The universal types lead the constant, in DEMOMA-16-001 order, and none is
    repeated further down among the scenario-specific entries (AC-3 of
    ISSUE-2266): a duplicated presence check adds no coverage and hides which
    block owns the requirement.
    """
    module = importlib.import_module(module_name)
    const_name, event_types = _expected_event_types_constant(module)
    where = f"{const_name} ({demo})"

    assert (
        tuple(event_types[: len(_UNIVERSAL_EVENT_TYPES)])
        == _UNIVERSAL_EVENT_TYPES
    ), (
        f"{where} must open with the DEMOMA-16-001 universal block "
        f"{list(_UNIVERSAL_EVENT_TYPES)}; got {event_types}"
    )

    for event_type in _UNIVERSAL_EVENT_TYPES:
        assert event_types.count(event_type) == 1, (
            f"{where} lists {event_type!r} {event_types.count(event_type)} "
            "times; universal types belong in the universal block exactly once"
        )


def test_all_ci_scenarios_have_a_harness_module() -> None:
    """Every CI-matrix entry names a harness file that exists.

    The count is pinned because the nine scenarios are enumerated by name in
    DEMOMA-16-002…-011 and in the tables in ``notes/demo-ci-invariants.md`` and
    ``notes/demo-ci-scenario-coverage.md``.  Adding a scenario means updating
    those too, so it should not pass here silently.
    """
    entries = json.loads(_CI_SCENARIOS_JSON.read_text())
    assert len(entries) == 9, (
        f"expected 9 CI scenarios, got {len(entries)} — if a scenario was "
        "added or removed, update DEMOMA-16 and the notes/ scenario tables"
    )
    missing = [
        entry["test_file"]
        for entry in entries
        if not (_REPO_ROOT / entry["test_file"]).is_file()
    ]
    assert not missing, f"CI matrix names nonexistent harness files: {missing}"


def test_demoma_16_001_enumerates_the_universal_types() -> None:
    """DEMOMA-16-001's statement names exactly the five universal types.

    Guards the spec side of DEMOMA-16-008: promoting or retiring a universal
    event type in the harnesses without amending DEMOMA-16-001 fails here.
    """
    statement = load_registry(_SPECS_DIR).get("DEMOMA-16-001").statement
    quoted = set(re.findall(r"`([a-z_]+)`", statement))
    assert quoted == set(_UNIVERSAL_EVENT_TYPES), (
        "DEMOMA-16-001 must enumerate exactly the universal event types "
        f"{sorted(_UNIVERSAL_EVENT_TYPES)}; its statement names "
        f"{sorted(quoted)}"
    )
