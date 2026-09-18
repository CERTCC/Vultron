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

from test.ci.invariants.universal_harness import make_universal_invariant_tests

_REPO_ROOT = Path(__file__).parents[3]
_DIAGNOSTIC_MAP = _REPO_ROOT / "notes" / "demo-ci-diagnostics.md"
_CI_SCENARIOS_JSON = _REPO_ROOT / ".github" / "demo-scenarios.json"
_MAP_HEADING = "### Invariant Status and Diagnostic Focus"

#: A table row: ``| 7 | `test_...` | ⏳ xfail — #2505 | 1 — Sent |``.
_ROW_RE = re.compile(
    r"^\|[^|]*\|\s*`(?P<fn>test_invariant_[a-z0-9_]+)`\s*\|"
    r"(?P<status>[^|]*)\|(?P<layer>[^|]*)\|\s*$"
)
#: An ATX heading, so a ``#`` comment inside a fenced block is not mistaken
#: for the end of the section (a real hazard: the section above the table
#: contains a bash fence whose lines start with ``#``).
_HEADING_RE = re.compile(r"^#{1,6}\s")
_ISSUE_RE = re.compile(r"#(\d+)")


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
        "(#, Test function, Status, Start at Layer) with the function name in "
        "backticks — update the regex if the columns changed"
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

    says_xfail = "xfail" in status.lower()
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


def _harness_files() -> list[pytest.param]:  # type: ignore[valid-type]
    """One param per CI-matrix scenario, naming its harness file.

    Reads ``.github/demo-scenarios.json`` — the sole scenario→harness registry.
    Do not add a second list of harness files here.
    """
    entries = json.loads(_CI_SCENARIOS_JSON.read_text(encoding="utf-8"))
    return [
        pytest.param(entry["test_file"], id=entry["demo"]) for entry in entries
    ]


@pytest.mark.parametrize("test_file", _harness_files())
def test_every_harness_passes_a_narrative_path(test_file: str) -> None:
    """Each harness supplies ``narrative_path`` to the factory.

    Without it the factory omits ``test_invariant_16_causal_edges_in_ledger_order``
    (DEMOMA-22-005) for that scenario.  Nothing else notices: the harness still
    collects, still passes, and the diagnostic map still lists invariant 16 as
    active — so the scenario quietly loses its causal-edge check.  This is the
    only invariant whose *presence* is conditional, which is why it gets its own
    assertion instead of being covered by the map comparison above.

    Parsed from source rather than imported: importing a harness executes
    ``globals().update(...)``, and the argument is what is under test, so
    reading the call site is both cheaper and more direct.
    """
    source = (_REPO_ROOT / test_file).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=test_file)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "make_universal_invariant_tests"
    ]
    assert len(calls) == 1, (
        f"{test_file} calls make_universal_invariant_tests() {len(calls)} "
        "times; expected exactly one call at module scope"
    )
    kwargs = {kw.arg for kw in calls[0].keywords}
    assert "narrative_path" in kwargs, (
        f"{test_file} calls make_universal_invariant_tests() without "
        "narrative_path, so this scenario silently gets no invariant 16 "
        "(causal-edge ordering, DEMOMA-22-005). Pass "
        'narrative_path="docs/topics/scenarios/<scenario>.md".'
    )
