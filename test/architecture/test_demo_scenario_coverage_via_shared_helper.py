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

"""Architecture invariant (DEMOMA-23-006): a scenario module never reads the
authority's ledger tail or polls a replica for contiguous coverage itself.

Every wait for a set of replicas to cover an authority's tail — the causal
gate before the notes phase and the temporal check after case closure — goes
through ``wait_for_replica_ledger_coverage`` in ``vultron/demo/helpers/sync.py``
(DEMOMA-23-005), and the sync-verification phase itself through
``run_sync_verification_phase`` (DEMOMA-23-007).  Before #3846 every scenario
module carried two copies of that loop, which is why one race-window fix had
to touch most of them and why their timeouts drifted (Concern #3042).

The forbidden names are the two primitives the spec itself lists.  Both a
direct call and an import are flagged: an import is how the call gets there,
and flake8 would only report it once it went unused.

Spec: ``specs/multi-actor-demo.yaml`` DEMOMA-23-005, DEMOMA-23-006, DEMOMA-23-007.
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_SCENARIO_DIR = _corpus.REPO_ROOT / "vultron" / "demo" / "scenario"
_SYNC = _corpus.REPO_ROOT / "vultron" / "demo" / "helpers" / "sync.py"

#: The loop primitives DEMOMA-23-006 forbids a scenario module to call.
_FORBIDDEN = frozenset(
    {"wait_for_contiguous_ledger_coverage", "_get_log_entries_for_case"}
)

#: The shared helpers every scenario routes those waits through.
_SHARED_HELPERS = frozenset(
    {"wait_for_replica_ledger_coverage", "run_sync_verification_phase"}
)


def _callee_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return getattr(func, "id", "")


def _forbidden_references(tree: ast.AST) -> list[tuple[int, str, str]]:
    """Return ``(line, kind, name)`` for every forbidden call or import."""
    hits: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _callee_name(node)
            if name in _FORBIDDEN:
                hits.append((node.lineno, "call", name))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _FORBIDDEN:
                    hits.append((node.lineno, "import", alias.name))
    return hits


_SCENARIO_TREES = {
    path: tree
    for path, tree in _corpus.all_trees(under=_SCENARIO_DIR)
    if path.name != "__init__.py"
}


def test_scenario_corpus_is_not_empty():
    """Guard: an empty corpus would make the per-module check vacuous."""
    assert len(_SCENARIO_TREES) >= 9, sorted(_SCENARIO_TREES)


@pytest.mark.parametrize(
    "scenario", sorted(_SCENARIO_TREES), ids=lambda p: p.name
)
def test_scenario_module_routes_coverage_waits_through_shared_helper(
    scenario: Path,
):
    """No scenario module calls or imports the coverage-loop primitives.

    Route the wait through ``wait_for_replica_ledger_coverage`` (closure phase)
    or ``run_sync_verification_phase`` (sync-verification phase) instead
    (DEMOMA-23-005, DEMOMA-23-006, DEMOMA-23-007).
    """
    hits = _forbidden_references(_SCENARIO_TREES[scenario])
    assert not hits, (
        f"{scenario.relative_to(_corpus.REPO_ROOT)} references the ledger "
        f"coverage primitives directly: {hits}. A scenario module MUST NOT "
        "call wait_for_contiguous_ledger_coverage or _get_log_entries_for_case "
        "(DEMOMA-23-006); use wait_for_replica_ledger_coverage / "
        "run_sync_verification_phase from vultron.demo.helpers.sync."
    )


def test_shared_helpers_exist_in_sync_module():
    """The helpers the ratchet points at are defined where the spec says."""
    defined = {
        node.name
        for path, tree in _corpus.files_mentioning(
            "def wait_for_replica_ledger_coverage", under=_SYNC.parent
        )
        if path == _SYNC
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }
    assert _SHARED_HELPERS <= defined, (
        f"{_SYNC} must define {sorted(_SHARED_HELPERS)} (DEMOMA-23-005, "
        f"DEMOMA-23-007); found {sorted(defined & _SHARED_HELPERS)}"
    )


def test_the_check_can_actually_fail():
    """Guard: the detector flags a direct call and a direct import."""
    sample = _corpus.parse_inline(
        "from vultron.demo.helpers.sync import _get_log_entries_for_case\n"
        "def _phase_case_closure(client, case):\n"
        "    entries = _get_log_entries_for_case(client, case.id_)\n"
        "    wait_for_contiguous_ledger_coverage(\n"
        "        client=client, case_id=case.id_, expected_tail_index=3\n"
        "    )\n"
    )
    hits = _forbidden_references(sample)
    assert sorted(h[1:] for h in hits) == [
        ("call", "_get_log_entries_for_case"),
        ("call", "wait_for_contiguous_ledger_coverage"),
        ("import", "_get_log_entries_for_case"),
    ]


def test_the_check_passes_for_the_shared_helper_call():
    """Guard: a call to the shared helper is not a violation."""
    sample = _corpus.parse_inline(
        "from vultron.demo.helpers.sync import wait_for_replica_ledger_coverage\n"
        "def _phase_case_closure(client, case):\n"
        "    wait_for_replica_ledger_coverage(\n"
        "        auth_client=client, replicas=[(client, 'Finder')],\n"
        "        case_id=case.id_, phase_label='close phase', causal=False,\n"
        "    )\n"
    )
    assert not _forbidden_references(sample)
