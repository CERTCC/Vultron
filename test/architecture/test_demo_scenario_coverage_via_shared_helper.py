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

"""Architecture invariant (DEMOMA-23-006): no module under ``vultron/demo/``
other than ``helpers/sync.py`` reads the authority's ledger tail or polls a
replica for contiguous coverage itself.

Every wait for a set of replicas to cover an authority's tail — the Phase 1
drain, the causal gate before the notes phase and the temporal check after
case closure — goes through ``wait_for_replica_ledger_coverage`` in
``vultron/demo/helpers/sync.py`` (DEMOMA-23-005), and the sync-verification
phase itself through ``run_sync_verification_phase`` (DEMOMA-23-007).  Before
#3846 every scenario module carried two copies of that loop, which is why one
race-window fix had to touch most of them and why their timeouts drifted
(Concern #3042).  When this ratchet covered scenario modules only, a third
copy (``drain_phase1_ledger`` in ``helpers/polling.py``) survived the
consolidation because a copy moved into a helper module was invisible to it
(#3906) — so the corpus is now every module under ``vultron/demo/``.

The forbidden names are the two primitives the spec itself lists.  A direct
call, an import (however aliased) and any other reference to the name — a
bound alias, an attribute read off the polling module, a ``functools.partial``
argument — are all flagged: each is how the call gets there, and flake8 would
only report the import once it went unused.  Two uses are exempt, as the spec
says: the primitive's own ``def`` (a ``FunctionDef`` name is not a reference)
and a ``from … import`` in a package ``__init__`` (a re-export, not a call).

Spec: ``specs/multi-actor-demo.yaml`` DEMOMA-23-005, DEMOMA-23-006, DEMOMA-23-007.
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_DEMO_DIR = _corpus.REPO_ROOT / "vultron" / "demo"
_SCENARIO_DIR = _DEMO_DIR / "scenario"
_POLLING = _DEMO_DIR / "helpers" / "polling.py"
_SYNC = _DEMO_DIR / "helpers" / "sync.py"

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


def _call_and_import_hits(
    tree: ast.AST,
) -> tuple[list[tuple[int, str, str]], set[int]]:
    """Forbidden names in call position or ``from … import``, plus callee ids."""
    hits: list[tuple[int, str, str]] = []
    callees: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            callees.add(id(node.func))
            name = _callee_name(node)
            if name in _FORBIDDEN:
                hits.append((node.lineno, "call", name))
        elif isinstance(node, ast.ImportFrom):
            hits.extend(
                (node.lineno, "import", alias.name)
                for alias in node.names
                if alias.name in _FORBIDDEN
            )
    return hits, callees


def _reference_name(node: ast.Name | ast.Attribute) -> str:
    """The name a ``Name`` or ``Attribute`` node spells."""
    return node.id if isinstance(node, ast.Name) else node.attr


def _forbidden_references(tree: ast.AST) -> list[tuple[int, str, str]]:
    """Return ``(line, kind, name)`` for every forbidden reference.

    ``kind`` is ``"call"`` for a name in call position, ``"import"`` for a
    ``from … import`` of the name (under any alias), and ``"reference"`` for
    any other ``Name`` or ``Attribute`` that spells it — the forms a call is
    smuggled through when it is not made directly.
    """
    hits, callees = _call_and_import_hits(tree)
    hits.extend(
        (node.lineno, "reference", _reference_name(node))
        for node in ast.walk(tree)
        if isinstance(node, (ast.Name, ast.Attribute))
        and id(node) not in callees
        and _reference_name(node) in _FORBIDDEN
    )
    return sorted(hits)


def _violations(path: Path, tree: ast.AST) -> list[tuple[int, str, str]]:
    """Forbidden references in *path*, minus the two exemptions DEMOMA-23-006 grants.

    A package ``__init__`` may ``from … import`` either name to re-export it;
    a call or any other reference there is still a violation.  The primitive's
    own ``def`` never appears here: a ``FunctionDef`` name is not a ``Name`` or
    ``Attribute`` node, so :func:`_forbidden_references` does not see it.
    """
    hits = _forbidden_references(tree)
    if path.name == "__init__.py":
        hits = [hit for hit in hits if hit[1] != "import"]
    return hits


_DEMO_TREES = {
    path: tree
    for path, tree in _corpus.all_trees(under=_DEMO_DIR)
    if path != _SYNC
}


def _module_id(path: Path) -> str:
    return path.relative_to(_DEMO_DIR).as_posix()


def test_demo_corpus_covers_scenarios_and_helpers():
    """Guard: the corpus is every module under ``vultron/demo/`` but ``sync.py``.

    A corpus that silently shrank back to the scenario directory is exactly
    how the third copy of the loop went unseen (#3906), so both the scenario
    modules and the helper that defines the primitive must be present, and
    the one exempt module must be absent.
    """
    assert len(_DEMO_TREES) >= 40, sorted(_DEMO_TREES)
    assert _POLLING in _DEMO_TREES
    assert _SYNC not in _DEMO_TREES
    scenario_modules = [
        p
        for p in _DEMO_TREES
        if p.parent == _SCENARIO_DIR and p.name != "__init__.py"
    ]
    assert len(scenario_modules) >= 9, sorted(scenario_modules)


@pytest.mark.parametrize("module", sorted(_DEMO_TREES), ids=_module_id)
def test_demo_module_routes_coverage_waits_through_shared_helper(module: Path):
    """No module under ``vultron/demo/`` calls or imports the coverage-loop primitives.

    Route the wait through ``wait_for_replica_ledger_coverage`` (Phase 1 drain
    and closure phase) or ``run_sync_verification_phase`` (sync-verification
    phase) instead (DEMOMA-23-005, DEMOMA-23-006, DEMOMA-23-007).  This covers
    helper modules too: a copy of the loop moved into one is the same defect
    as a copy in a scenario (#3906).
    """
    hits = _violations(module, _DEMO_TREES[module])
    assert not hits, (
        f"{module.relative_to(_corpus.REPO_ROOT)} references the ledger "
        f"coverage primitives directly: {hits}. A module under vultron/demo/ "
        "other than helpers/sync.py MUST NOT call or import "
        "wait_for_contiguous_ledger_coverage or _get_log_entries_for_case "
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


def test_the_check_flags_smuggled_references():
    """Guard: an aliased import, a bound name and an attribute read are hits."""
    sample = _corpus.parse_inline(
        "import functools\n"
        "from vultron.demo.helpers import polling\n"
        "from vultron.demo.helpers.sync import (\n"
        "    _get_log_entries_for_case as read_tail,\n"
        ")\n"
        "def _phase_case_closure(client, case):\n"
        "    wait = polling.wait_for_contiguous_ledger_coverage\n"
        "    entries = read_tail(client, case.id_)\n"
        "    later = functools.partial(\n"
        "        polling.wait_for_contiguous_ledger_coverage, client=client\n"
        "    )\n"
        "    return wait, entries, later\n"
    )
    hits = _forbidden_references(sample)
    assert sorted(h[1:] for h in hits) == [
        ("import", "_get_log_entries_for_case"),
        ("reference", "wait_for_contiguous_ledger_coverage"),
        ("reference", "wait_for_contiguous_ledger_coverage"),
    ]


def test_the_check_flags_a_helper_module_copy_of_the_loop():
    """Guard: the loop copied into a helper module is flagged (#3906).

    This is the shape ``drain_phase1_ledger`` had in ``helpers/polling.py``: a
    lazy in-function import of the tail reader plus a direct call to the
    coverage primitive, wrapped in its own ``demo_gate``.  Being wrapped is
    not the point — being a second copy of the loop is.
    """
    sample = _corpus.parse_inline(
        "def drain_phase1_ledger(auth_client, case_id, replica_pairs):\n"
        "    from vultron.demo.helpers.sync import _get_log_entries_for_case\n"
        "    from vultron.demo.utils import demo_gate\n"
        "    entries = _get_log_entries_for_case(auth_client, case_id)\n"
        "    if not entries:\n"
        "        return\n"
        "    tail_index = max(e['log_index'] for e in entries)\n"
        "    for replica_client, label in replica_pairs:\n"
        "        with demo_gate(f'{label} ledger coverage'):\n"
        "            wait_for_contiguous_ledger_coverage(\n"
        "                client=replica_client, case_id=case_id,\n"
        "                expected_tail_index=tail_index,\n"
        "            )\n",
        filename="vultron/demo/helpers/polling.py",
    )
    hits = _violations(_POLLING, sample)
    assert sorted(h[1:] for h in hits) == [
        ("call", "_get_log_entries_for_case"),
        ("call", "wait_for_contiguous_ledger_coverage"),
        ("import", "_get_log_entries_for_case"),
    ]


def test_the_primitive_definition_is_not_a_violation():
    """Guard: ``def wait_for_contiguous_ledger_coverage`` in polling.py is exempt."""
    sample = _corpus.parse_inline(
        "def wait_for_contiguous_ledger_coverage(client, case_id, "
        "expected_tail_index, timeout_seconds=15.0):\n"
        "    _poll_until(lambda: True, timeout_seconds, 0.5, 'msg')\n"
    )
    assert not _violations(_POLLING, sample)


def test_package_init_may_re_export_but_not_call():
    """Guard: a ``from … import`` in ``__init__.py`` is exempt; a call is not."""
    init = _DEMO_DIR / "helpers" / "__init__.py"
    re_export = _corpus.parse_inline(
        "from vultron.demo.helpers.polling import (  # noqa: F401\n"
        "    wait_for_contiguous_ledger_coverage,\n"
        ")\n"
        "from vultron.demo.helpers.sync import (  # noqa: F401\n"
        "    _get_log_entries_for_case,\n"
        ")\n"
    )
    assert not _violations(init, re_export)
    # The same import is a violation in any module that is not an __init__.
    assert [h[1:] for h in _violations(_POLLING, re_export)] == [
        ("import", "wait_for_contiguous_ledger_coverage"),
        ("import", "_get_log_entries_for_case"),
    ]
    calling_init = _corpus.parse_inline(
        "from vultron.demo.helpers.sync import _get_log_entries_for_case\n"
        "TAIL = _get_log_entries_for_case(None, 'urn:case')\n"
    )
    assert [h[1:] for h in _violations(init, calling_init)] == [
        ("call", "_get_log_entries_for_case"),
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
