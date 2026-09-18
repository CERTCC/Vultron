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
"""Ratchet: the diagnostic map matches the universal invariant factory.

``notes/demo-ci-diagnostics.md`` § "Per-Invariant Diagnostic Map" is what an
agent reads to triage a red ``Invariant Harness`` job: which invariant failed,
whether a known defect already owns it, and which of the three diagnostic
layers to check first.  When the table drifts from
``make_universal_invariant_tests()`` it does not merely go quiet — it actively
misdirects the investigation, sending the agent to a closed issue or omitting
the invariant that actually failed.

Nothing enforced that correspondence, and it rotted: the table went on citing
#789/#791/#937 long after all three closed, listed several invariants as
``xfail`` that had since been promoted to active guards, and omitted the ones
added after it was written (ISSUE-3337).  These tests close the gap without
needing any demo artifact, so they run in the ordinary unit suite.

The factory is the source of truth in both directions: an invariant added or
retired there fails here until the table follows, and a row for an invariant
the factory does not inject fails too.

Two escape hatches would let ratchet state hide where the table cannot show it,
so both are closed here rather than left to prose:

* a ``marks=`` entry on one of the ``pytest.param`` lists the factory
  parametrizes over, which would xfail *some cases* of a row the table calls
  ``active`` — see ``test_no_param_level_marks_on_factory_arguments``;
* a ``narrative_path`` that does not resolve, which makes invariant 16 skip
  rather than run — see ``test_every_harness_passes_a_narrative_path``.

Deliberately *not* checked: whether an invariant passes today.  That is a
property of a demo run, not of the source, so no ratchet can hold it and the
table does not claim it.  Status here means the ratchet state — ``xfail`` or
active — which is exactly what the markers encode.
"""

from __future__ import annotations

import ast
import functools
import json
import re
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import pytest
import yaml
from _pytest.mark.structures import ParameterSet

from test.ci.invariants.universal_harness import make_universal_invariant_tests

_REPO_ROOT = Path(__file__).parents[3]
_DIAGNOSTIC_MAP = _REPO_ROOT / "notes" / "demo-ci-diagnostics.md"
_CI_SCENARIOS_JSON = _REPO_ROOT / ".github" / "demo-scenarios.json"
_MAP_HEADING = "### Invariant Status and Diagnostic Focus"

#: A table row: ``| 7 | `test_...` | ⏳ xfail — #2505 | 1 — Sent |``.  The
#: function-name pattern is deliberately wider than ``test_invariant_*``: three
#: rows are named for a spec clause or a property instead, and a stricter
#: pattern would report a present row as missing.
_ROW_RE = re.compile(
    r"^\|[^|]*\|\s*`(?P<fn>test_[a-z0-9_]+)`\s*\|"
    r"(?P<status>[^|]*)\|(?P<layer>[^|]*)\|\s*$"
)
#: An ATX heading, used to find the end of the table's section.  Note this
#: matches a ``#`` comment inside a fenced code block too, so the table's
#: section must not contain one; what the trailing ``\s`` buys is that a
#: line-initial issue reference such as ``#2505`` is not read as a heading.
_HEADING_RE = re.compile(r"^#{1,6}\s")
_ISSUE_RE = re.compile(r"#(\d+)")

#: The only two legal Status cells.  A controlled vocabulary rather than an
#: ``"xfail" in cell`` substring test: a cell reading ``active (was xfail under
#: #789)`` satisfies the substring test while meaning the opposite, and would
#: be reported as the wrong defect.
_STATUS_ACTIVE = "active"
_STATUS_XFAIL_RE = re.compile(r"^⏳ xfail — #\d+$")

#: YAML front-matter block at the top of a scenario narrative page.
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

#: The harness constants whose ``pytest.param`` entries become per-case
#: parametrization of the universal invariants (``_CHAIN_ACTORS``,
#: ``_FV_EXPECTED_EVENT_TYPES``, ...).
_PARAM_CONSTANT_RE = re.compile(
    r"^_(CHAIN_ACTORS|[A-Z0-9_]+_EXPECTED_EVENT_TYPES)$"
)


def _called_name(func: ast.expr) -> str | None:
    """The bare name of a call target, whether bare or module-qualified."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


@functools.cache
def _factory_invariants() -> Mapping[str, str | None]:
    """Return ``{test function name: xfail reason or None}``.

    Arguments are placeholders: the factory builds closures without touching
    them, so no fixture, devlog, or narrative file is needed.  ``narrative_path``
    is supplied because every real harness supplies one — which is what makes
    invariant 16 part of the universal set in practice, and is itself asserted
    by ``test_every_harness_passes_a_narrative_path``.

    Read-only: the result is cached and shared across every test in the module.
    """
    tests = make_universal_invariant_tests(
        replicas_fixture="_unused_replicas",
        chain_actors=["case-actor"],
        expected_event_types=["validate_report"],
        narrative_path="docs/topics/scenarios/fv.md",
    )
    invariants: dict[str, str | None] = {}
    for name, fn in tests.items():
        xfail = [
            mark
            for mark in getattr(fn, "pytestmark", [])
            if mark.name == "xfail"
        ]
        assert len(xfail) <= 1, f"{name} carries {len(xfail)} xfail markers"
        if xfail:
            marker = xfail[0]
            # A conditional xfail has no single truthful Status cell: the table
            # would have to print "xfail" for a test pytest may well run and
            # report normally.  Reject the form rather than record a claim that
            # is only sometimes true.
            assert not marker.args and "condition" not in marker.kwargs, (
                f"{name} carries a *conditional* xfail marker, which the "
                "diagnostic map cannot represent — its Status column records "
                "one unconditional xfail-or-active state per invariant. Move "
                "the condition into the check itself, or drop it."
            )
        invariants[name] = (
            str(xfail[0].kwargs.get("reason", "")) if xfail else None
        )
    return MappingProxyType(invariants)


@functools.cache
def _map_rows() -> Mapping[str, str]:
    """Return ``{test function name: Status cell}`` from the diagnostic map.

    Only lines under ``_MAP_HEADING`` and above the next ATX heading are read,
    so function names in the surrounding prose — the scenario-local late-joiner
    tests, for instance — are not mistaken for rows.

    Read-only: the result is cached and shared across every test in the module.
    """
    text = _DIAGNOSTIC_MAP.read_text(encoding="utf-8")
    assert _MAP_HEADING in text, (
        f"{_DIAGNOSTIC_MAP.name} no longer contains {_MAP_HEADING!r}; "
        "this ratchet cannot locate the table"
    )
    lines = text.split(_MAP_HEADING, 1)[1].splitlines()
    for end, line in enumerate(lines):
        if _HEADING_RE.match(line):
            lines = lines[:end]
            break

    rows: dict[str, str] = {}
    header_seen = False
    for line in lines:
        header_seen = header_seen or line.startswith("| # |")
        match = _ROW_RE.match(line)
        if match is None:
            continue
        name = match.group("fn")
        assert name not in rows, f"{name} appears in the map table twice"
        rows[name] = match.group("status").strip()
    # Distinguish "the table moved or changed shape" from "the table is empty":
    # _ROW_RE hard-codes four columns, so adding a fifth silently matches
    # nothing and would otherwise surface as a bare "no rows parsed".
    assert header_seen, (
        f"no '| # |' header row found under {_MAP_HEADING!r} in "
        f"{_DIAGNOSTIC_MAP.name}; the table was moved, renamed, or removed"
    )
    assert rows, (
        f"the table under {_MAP_HEADING!r} in {_DIAGNOSTIC_MAP.name} has a "
        "header but no parseable rows; _ROW_RE expects exactly four columns "
        "(#, Test function, Status, Start at Layer) with a `test_`-prefixed "
        "function name in backticks — update the regex if that changed"
    )
    return MappingProxyType(rows)


def test_diagnostic_map_lists_every_universal_invariant() -> None:
    """The map's rows are exactly the invariants the factory injects."""
    expected = set(_factory_invariants())
    listed = set(_map_rows())

    missing = sorted(expected - listed)
    extra = sorted(listed - expected)
    assert not missing and not extra, (
        f"{_DIAGNOSTIC_MAP.name} § 'Per-Invariant Diagnostic Map' is out of "
        "step with make_universal_invariant_tests(): "
        f"missing rows for {missing}; rows for non-existent invariants {extra}"
    )


@pytest.mark.parametrize("name", sorted(_factory_invariants()))
def test_diagnostic_map_status_matches_xfail_markers(name: str) -> None:
    """A row says ``xfail`` iff the injected test carries an xfail marker."""
    reason = _factory_invariants()[name]
    status = _map_rows().get(name)
    assert status is not None, f"{name} has no row in {_DIAGNOSTIC_MAP.name}"

    if status == _STATUS_ACTIVE:
        says_xfail = False
    elif _STATUS_XFAIL_RE.match(status):
        says_xfail = True
    else:
        raise AssertionError(
            f"{name}: Status cell {status!r} is neither {_STATUS_ACTIVE!r} nor "
            "of the form '⏳ xfail — #N'. Those are the only two states an "
            "xfail marker can express, and anything else is ambiguous — "
            "'active (was xfail under #789)' reads as both at once."
        )

    if reason is None:
        assert not says_xfail, (
            f"{name} has no xfail marker but the diagnostic map records "
            f"{status!r}; a stale xfail row hides a live regression guard"
        )
        return

    assert says_xfail, (
        f"{name} is xfail'ed in universal_harness.py "
        f"(reason: {reason!r}) but the diagnostic map records {status!r}"
    )


@pytest.mark.parametrize("name", sorted(_factory_invariants()))
def test_diagnostic_map_cites_the_owning_issue(name: str) -> None:
    """An xfail row names the same issue the marker's ``reason`` names.

    The failure mode this catches is the one that made ISSUE-3337 necessary:
    a row that still points triage at an issue closed several releases ago.
    """
    reason = _factory_invariants()[name]
    if reason is None:
        pytest.skip(f"{name} is active; no owning issue to cite")

    marker_issues = set(_ISSUE_RE.findall(reason))
    assert marker_issues, (
        f"{name}'s xfail reason names no issue: {reason!r}. Name the owning "
        "issue so triage has somewhere to go."
    )
    row_issues = set(_ISSUE_RE.findall(_map_rows()[name]))
    assert row_issues & marker_issues, (
        f"{name}: the diagnostic map cites {sorted(row_issues) or 'no issue'} "
        f"but the xfail marker names {sorted(marker_issues)}"
    )


def _registry_entries() -> list[dict]:
    """The ``.github/demo-scenarios.json`` entries that are JSON objects.

    That file is the sole scenario→harness registry. Do not add a second list
    of harness files here.
    """
    raw = json.loads(_CI_SCENARIOS_JSON.read_text(encoding="utf-8"))
    return [entry for entry in raw if isinstance(entry, dict)]


def _harness_files() -> list[ParameterSet]:
    """One param per CI-matrix scenario: ``(demo, test_file)``.

    Reads the registry with ``.get()`` rather than indexing, so a malformed
    entry fails that scenario's own case — and
    ``test_scenario_registry_is_well_formed`` — instead of raising during
    collection and taking every other assertion in this module down with it.
    """
    return [
        pytest.param(
            entry.get("demo"),
            entry.get("test_file"),
            id=str(entry.get("demo") or f"entry-{index}"),
        )
        for index, entry in enumerate(_registry_entries())
    ]


def _harness_tree(demo: str | None, test_file: str | None) -> ast.Module:
    """Parse a registered harness file, asserting the registry points at it."""
    assert test_file, f"scenario {demo!r} has no 'test_file' in the registry"
    path = _REPO_ROOT / test_file
    assert (
        path.is_file()
    ), f"scenario {demo!r} names a harness that does not exist: {test_file}"
    return ast.parse(path.read_text(encoding="utf-8"), filename=test_file)


def _narrative_edges(page: Path) -> list[dict]:
    """The ``causal_edges`` list from a narrative page's front matter."""
    match = _FRONTMATTER_RE.match(page.read_text(encoding="utf-8"))
    if match is None:
        return []
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        return []
    return [e for e in data.get("causal_edges") or [] if isinstance(e, dict)]


def test_scenario_registry_is_well_formed() -> None:
    """Every registry entry names a demo and an existing harness file, once."""
    raw = json.loads(_CI_SCENARIOS_JSON.read_text(encoding="utf-8"))
    entries = _registry_entries()
    assert entries, f"{_CI_SCENARIOS_JSON.name} registers no scenarios"
    assert len(entries) == len(raw), (
        f"{_CI_SCENARIOS_JSON.name} has {len(raw) - len(entries)} entries "
        "that are not JSON objects"
    )

    demos = [entry.get("demo") for entry in entries]
    files = [entry.get("test_file") for entry in entries]
    assert all(demos), f"registry entries missing a 'demo' key: {demos}"
    assert all(files), f"registry entries missing a 'test_file' key: {files}"
    assert len(set(demos)) == len(demos), f"duplicate 'demo' names: {demos}"
    assert len(set(files)) == len(
        files
    ), f"duplicate 'test_file' paths: {files}"

    missing = [f for f in files if not (_REPO_ROOT / str(f)).is_file()]
    assert (
        not missing
    ), f"{_CI_SCENARIOS_JSON.name} names missing harness files: {missing}"


@pytest.mark.parametrize(("demo", "test_file"), _harness_files())
def test_every_harness_passes_a_narrative_path(
    demo: str | None,
    test_file: str | None,
) -> None:
    """Each harness supplies a ``narrative_path`` that actually yields edges.

    Without the argument the factory omits
    ``test_invariant_16_causal_edges_in_ledger_order`` (DEMOMA-22-005) for that
    scenario.  Nothing else notices: the harness still collects, still passes,
    and the diagnostic map still lists invariant 16 as active — so the scenario
    quietly loses its causal-edge check.  This is the only invariant whose
    *presence* is conditional, which is why it gets its own assertion instead
    of being covered by the map comparison above.

    The **value** is checked, not just the keyword's presence, because a
    ``narrative_path`` that does not resolve fails just as quietly and more
    plausibly — rename the page, or drop its ``causal_edges:`` block, and
    ``load_narrative_edges()`` calls ``pytest.skip()`` rather than failing, so
    the injected test evaporates into a skip.

    Parsed from source rather than imported: importing a harness executes
    ``globals().update(...)``, and the argument is what is under test, so
    reading the call site is both cheaper and more direct.
    """
    tree = _harness_tree(demo, test_file)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _called_name(node.func) == "make_universal_invariant_tests"
    ]
    assert len(calls) == 1, (
        f"{test_file} calls make_universal_invariant_tests() {len(calls)} "
        "times; expected exactly one call at module scope"
    )

    keywords = {kw.arg: kw.value for kw in calls[0].keywords}
    assert "narrative_path" in keywords, (
        f"{test_file} calls make_universal_invariant_tests() without "
        "narrative_path, so this scenario silently gets no invariant 16 "
        "(causal-edge ordering, DEMOMA-22-005). Pass "
        'narrative_path="docs/topics/scenarios/<scenario>.md".'
    )

    node = keywords["narrative_path"]
    assert (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value
    ), (
        f"{test_file} passes a narrative_path this ratchet cannot resolve: "
        f"{ast.unparse(node)}. Pass a literal string — a None or computed "
        "value would drop invariant 16 (or skip it) without failing anything."
    )

    page = _REPO_ROOT / node.value
    assert page.is_file(), (
        f"{test_file} passes narrative_path={node.value!r}, which does not "
        "exist. load_narrative_edges() skips rather than fails on a missing "
        "page, so invariant 16 would vanish from this scenario silently."
    )
    assert _narrative_edges(page), (
        f"{node.value} has no non-empty 'causal_edges:' front-matter block, "
        f"so invariant 16 skips for scenario {demo!r} instead of checking "
        "anything (DEMOMA-22-005)."
    )


@pytest.mark.parametrize(("demo", "test_file"), _harness_files())
def test_no_param_level_marks_on_factory_arguments(
    demo: str | None,
    test_file: str | None,
) -> None:
    """Ratchet state lives on the factory's closures, never on a param entry.

    The universal invariants are parametrized over each harness's
    ``_CHAIN_ACTORS`` and ``_<SCENARIO>_EXPECTED_EVENT_TYPES`` lists.  A
    ``pytest.param(..., marks=pytest.mark.xfail(...))`` entry in either list
    xfails *some cases* of an invariant the diagnostic map calls ``active``,
    and none of the assertions above can see it: the marker rides on the
    parameter, not on the function, so it never reaches ``pytestmark``.

    That is not hypothetical drift — it is the drift the retired table in
    ``test/ci/README-case-log-ratchet.md`` recorded as "✅ case-actor,
    ✅ vendor, ⏳ finder" for invariants 12 and 13.  The map has one Status
    cell per invariant and so cannot express a per-actor state; rather than let
    it under-report, the per-param form is rejected here.

    Scenario-local tests are untouched by this: only the two constants the
    factory consumes are read, and those tests are free to carry their own
    markers.
    """
    tree = _harness_tree(demo, test_file)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [
            target.id
            for target in node.targets
            if isinstance(target, ast.Name)
            and _PARAM_CONSTANT_RE.match(target.id)
        ]
        if not targets:
            continue
        for call in ast.walk(node.value):
            if not isinstance(call, ast.Call):
                continue
            if _called_name(call.func) != "param":
                continue
            for keyword in call.keywords:
                if keyword.arg == "marks":
                    offenders.append(
                        f"{targets[0]} line {call.lineno}: "
                        f"marks={ast.unparse(keyword.value)}"
                    )

    assert not offenders, (
        f"{test_file} attaches marks to a factory parametrization argument:\n"
        + "\n".join(f"  - {offender}" for offender in offenders)
        + "\n\nnotes/demo-ci-diagnostics.md records one xfail-or-active state "
        "per invariant, read off the factory's own markers, so a per-param "
        "mark makes that table silently wrong for the cases it covers. Put "
        "the xfail on the invariant in universal_harness.py and update the "
        "map, or make the check itself tolerate this actor or event type."
    )
