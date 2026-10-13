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

"""Ratchet: core builds no ``payloadSnapshot`` by hand (VM-08-003, #3743).

A ledger entry's ``payloadSnapshot`` is either the activity received, as
received, or an activity the CASE_MANAGER sends: the blob the factory built
and sealed (VM-08-003).  A dict literal shaped like an activity, with a
``"type"`` and an ``"actor"`` key, assembled in ``vultron/core/``, records an
activity nobody sent, which is what case closure and the late-Accept
acknowledgement did before #3743.

Every such literal is located by file and enclosing function and compared
to an exact baseline, so a new site fails and a removed one must be taken
out (the set may only shrink, ARCH-18-002).  Each baseline row names the
issue that removes it.
"""

import ast
from collections.abc import Iterator

from test.architecture import _corpus

_CORE = _corpus.REPO_ROOT / "vultron" / "core"

_REMAINDER = "#4584"

#: Activity-shaped dict literals still built in core, by ``(file, function)``.
#: Each row is removed by the issue it names; add none (VM-08-003).
_BASELINE: dict[tuple[str, str], str] = {
    (
        "vultron/core/behaviors/embargo/expiry_tree.py",
        "expiry_payload_snapshot",
    ): _REMAINDER,
    (
        "vultron/core/behaviors/embargo/expiry_tree.py",
        "honour_late_accept_payload_snapshot",
    ): _REMAINDER,
    (
        "vultron/core/behaviors/case/ledger_snapshots.py",
        "build_create_case_snapshot",
    ): _REMAINDER,
    (
        "vultron/core/behaviors/case/ledger_snapshots.py",
        "build_add_report_to_case_snapshot",
    ): _REMAINDER,
    (
        "vultron/core/behaviors/case/ledger_snapshots.py",
        "build_add_participant_status_snapshot",
    ): _REMAINDER,
    (
        "vultron/core/behaviors/case/ledger_snapshots.py",
        "build_add_case_status_snapshot",
    ): _REMAINDER,
    (
        "vultron/core/behaviors/case/ledger_snapshots.py",
        "build_create_case_participant_snapshot",
    ): _REMAINDER,
    (
        "vultron/core/behaviors/case_status_snapshot.py",
        "EmitCaseStatusUpdateNode.update",
    ): _REMAINDER,
    (
        "vultron/core/use_cases/triggers/sync_log_entry.py",
        "SvcSyncLogEntryUseCase._prepare",
    ): _REMAINDER,
}

_ACTIVITY_KEYS = frozenset({"type", "actor"})


def _constant_keys(node: ast.Dict) -> set[str]:
    return {
        key.value
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def _activity_literals(
    node: ast.AST, scope: tuple[str, ...] = ()
) -> Iterator[tuple[str, int]]:
    """``(enclosing qualname, line)`` of each activity-shaped dict literal."""
    for child in ast.iter_child_nodes(node):
        if isinstance(
            child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            yield from _activity_literals(child, (*scope, child.name))
            continue
        if (
            isinstance(child, ast.Dict)
            and _constant_keys(child) >= _ACTIVITY_KEYS
        ):
            yield ".".join(scope) or "<module>", _corpus.node_line(child)
        yield from _activity_literals(child, scope)


def _sites() -> dict[tuple[str, str], list[int]]:
    found: dict[tuple[str, str], list[int]] = {}
    for path, tree in _corpus.files_mentioning('"actor"', under=_CORE):
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        for qualname, line in _activity_literals(tree):
            found.setdefault((rel, qualname), []).append(line)
    return found


def test_the_scan_finds_a_known_site():
    """Guard against a vacuous pass: the scan sees a baseline row."""
    assert (
        "vultron/core/behaviors/embargo/expiry_tree.py",
        "expiry_payload_snapshot",
    ) in _sites()


def test_the_scan_sees_a_literal_inside_a_method():
    tree = _corpus.parse_inline(
        "class Node:\n"
        "    def update(self):\n"
        "        return {'type': 'Leave', 'actor': 'urn:a'}\n"
    )
    assert [q for q, _ in _activity_literals(tree)] == ["Node.update"]


def test_core_builds_no_new_payload_snapshot_by_hand():
    """Activity-shaped dict literals in core equal the baseline (VM-08-003)."""
    actual = _sites()
    added = {
        f"{path}::{qualname} (lines {lines})"
        for (path, qualname), lines in actual.items()
        if (path, qualname) not in _BASELINE
    }
    removed = {
        f"{path}::{qualname}"
        for (path, qualname) in _BASELINE
        if (path, qualname) not in actual
    }
    assert not added and not removed, (
        "Activity-shaped dict literals under vultron/core/ changed"
        " (VM-08-003).\n"
        f"  new (build the activity with a factory through"
        f" TriggerActivityPort and commit its sealed blob): {sorted(added)}\n"
        f"  gone (remove the baseline row): {sorted(removed)}"
    )


def test_each_baseline_row_names_its_issue():
    assert all(issue.startswith("#") for issue in _BASELINE.values())
