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
"""Architecture invariant: one BT execution per inbox delivery (CLP-10-005).

A received-side use case's ``execute()`` method MUST do exactly three
things: build one BT via a tree-factory function in
``vultron/core/behaviors/``, call ``BTBridge.execute_with_setup()`` exactly
once under ``actor_id=receiving_actor_id``, and handle the result.
``execute()`` MUST NOT contain any other domain-significant code — no
second BT execution, no direct DataLayer mutation, and no direct import of
``create_guarded_commit_case_ledger_entry_tree`` (or any other
guarded-commit factory). This grep is a proxy for that broader rule: it
catches every known violation, but fixing a violation may mean repairing
genuine actor-identity switching, moving non-BT procedural code into the
tree, or simply relocating an already-correct inline tree into a factory
function — see ADR-0022 for the per-site breakdown. A reviewer MUST still
confirm no other domain-significant code remains in ``execute()`` when
closing each migration; this test alone does not guarantee that.

Spec: CLP-10-005. Decision record: ADR-0022.

Ratchet pattern
---------------
``KNOWN_VIOLATIONS`` documents every pre-existing violation awaiting
migration (see issues #1036, #1047, and their implementation issues). The
test asserts::

    actual_violations == KNOWN_VIOLATIONS

This means:

* **Adding a new violation** causes the test to **fail** immediately.
* **Fixing a violation** also causes the test to **fail** until the
  resolved entry is removed from ``KNOWN_VIOLATIONS``.

Remove entries from ``KNOWN_VIOLATIONS`` one by one as each use case
migrates to the single-tree shape. When the set is empty, CLP-10-005 is
fully satisfied.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]  # test/architecture/ → test/ → repo root

_GUARDED_COMMIT_FACTORY = "create_guarded_commit_case_ledger_entry_tree"

_USE_CASES_ROOT = REPO_ROOT / "vultron" / "core" / "use_cases"


def _imports_guarded_commit_factory(source_path: Path) -> bool:
    """Return True if *source_path* imports the guarded-commit factory.

    Detects both top-level and deferred (local) ``from ... import`` of
    ``create_guarded_commit_case_ledger_entry_tree``.
    """
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == _GUARDED_COMMIT_FACTORY:
                    return True
    return False


def _collect_violations() -> frozenset[str]:
    """Return repo-relative paths of use-case files importing the factory."""
    violations: set[str] = set()
    for py_file in _USE_CASES_ROOT.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        if _imports_guarded_commit_factory(py_file):
            violations.add(py_file.relative_to(REPO_ROOT).as_posix())
    return frozenset(violations)


# ---------------------------------------------------------------------------
# Known pre-existing violations awaiting migration (issue #1036, ADR-0022).
# Remove entries one by one as each use case migrates to a single
# `execute_with_setup()` call with the guarded commit composed as a child
# subtree of the use case's own tree-factory function.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset(
    {
        "vultron/core/use_cases/received/embargo.py",
        "vultron/core/use_cases/received/report.py",
        "vultron/core/use_cases/received/note.py",
        "vultron/core/use_cases/received/status.py",
        "vultron/core/use_cases/received/case/lifecycle.py",
        "vultron/core/use_cases/received/actor/case_manager_role.py",
    }
)


def test_received_use_cases_do_not_dispatch_guarded_commit_directly():
    """vultron/core/use_cases/ must not import the guarded-commit factory.

    Spec: CLP-10-005. Decision record: ADR-0022.

    See module docstring for the ratchet strategy.
    """
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW violations (use cases must not import the guarded-commit"
            " factory directly):"
        )
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED violations (remove these entries from"
            " KNOWN_VIOLATIONS):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)
