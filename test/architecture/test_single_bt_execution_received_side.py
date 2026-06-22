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
"""Architecture invariants: one BT execution per inbox delivery (CLP-10-005).

Two complementary tests enforce the single-BT-execution contract for all
``execute()`` methods under ``vultron/core/use_cases/``.

**Proxy ratchet** (``test_received_use_cases_do_not_dispatch_guarded_commit_directly``)
  Detects direct imports of ``create_guarded_commit_case_ledger_entry_tree``
  in use-case files — a structural proxy for the "double BT execution"
  anti-pattern. Uses a ``KNOWN_VIOLATIONS`` escape hatch to track pre-existing
  sites awaiting migration. A reviewer MUST still confirm no other
  domain-significant code remains in ``execute()`` when closing each migration;
  this test alone does not guarantee that. See ADR-0022 for the per-site
  breakdown.

**Hard invariant** (``test_no_execute_method_calls_execute_with_setup_more_than_once``)
  Uses ``ast.walk`` to count ``execute_with_setup`` call sites directly inside
  each ``execute()`` method body. Asserts that the count is **≤ 1** for every
  method. Unlike the ratchet above, this test has **no** ``KNOWN_VIOLATIONS``
  escape hatch — it is an unconditional upper bound. The baseline is already
  clean (zero violations after #1052 / #1066), so the assertion ships
  unconditional.

A received-side use case's ``execute()`` method MUST do exactly three
things: build one BT via a tree-factory function in
``vultron/core/behaviors/``, call ``BTBridge.execute_with_setup()`` exactly
once under ``actor_id=receiving_actor_id``, and handle the result.

Spec: CLP-10-005. Decision record: ADR-0022.
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
KNOWN_VIOLATIONS: frozenset[str] = frozenset()


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


# ---------------------------------------------------------------------------
# Hard invariant: no execute() method may call execute_with_setup() more
# than once.  No KNOWN_VIOLATIONS escape hatch — this is unconditional.
# Spec: CLP-10-005. Decision record: ADR-0022.
# ---------------------------------------------------------------------------


def _is_execute_with_setup_call(node: ast.AST) -> bool:
    """Return True if *node* is a call expression targeting execute_with_setup."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute) and func.attr == "execute_with_setup"
    ) or (isinstance(func, ast.Name) and func.id == "execute_with_setup")


def _walk_own_scope(node: ast.AST):
    """Yield all descendants of *node* without crossing nested function scopes.

    Unlike ``ast.walk``, this generator stops descending when it encounters a
    ``FunctionDef`` or ``AsyncFunctionDef`` that is not the root *node* itself.
    This prevents calls inside inner helper functions defined inside
    ``execute()`` from being counted as direct calls of ``execute()``.
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Stop here: inner function bodies are a separate scope.
            continue
        yield from _walk_own_scope(child)


def _count_multi_execute_violations(source_path: Path) -> dict[str, int]:
    """Return ``'file:lineno' → call_count`` for every execute() method that
    calls execute_with_setup() more than once in its own scope.

    Only direct calls inside the ``execute()`` body are counted; calls inside
    nested helper functions defined within ``execute()`` are excluded.

    Returns an empty dict when no violations are found or on SyntaxError.
    """
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return {}

    results: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != "execute":
            continue
        count = sum(
            1
            for child in _walk_own_scope(node)
            if _is_execute_with_setup_call(child)
        )
        if count > 1:
            try:
                label = source_path.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                label = str(source_path)
            results[f"{label}:{node.lineno}"] = count

    return results


def test_no_execute_method_calls_execute_with_setup_more_than_once():
    """No execute() method in use_cases/ calls execute_with_setup() more than once.

    This is a hard invariant (CLP-10-005) with no KNOWN_VIOLATIONS escape hatch.
    The baseline is already clean after #1052 / #1066; any new violation causes
    an immediate failure.

    Spec: CLP-10-005. Decision record: ADR-0022.
    """
    violations: dict[str, int] = {}
    for py_file in _USE_CASES_ROOT.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        violations.update(_count_multi_execute_violations(py_file))

    assert not violations, (
        "execute() methods calling execute_with_setup() more than once"
        " (CLP-10-005 hard invariant):\n"
        + "\n".join(
            f"  {path}: {count} call(s)"
            for path, count in sorted(violations.items())
        )
    )


def test_detector_catches_synthetic_multi_execute_with_setup_violation(
    tmp_path: Path,
) -> None:
    """Confirm the AST scanner flags a synthetic double execute_with_setup call.

    AC-3: verifies that a future regression would be caught immediately, and
    that a single call in an inner helper function does NOT produce a false
    positive.
    """
    # Two direct calls in one execute() — should be flagged.
    violation_file = tmp_path / "synthetic_violation.py"
    violation_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        self.bridge.execute_with_setup(actor_id='a', bt=None)\n"
        "        self.bridge.execute_with_setup(actor_id='b', bt=None)\n",
        encoding="utf-8",
    )
    violations = _count_multi_execute_violations(violation_file)
    assert (
        violations
    ), "Detector did not flag the synthetic double execute_with_setup call"
    counts = list(violations.values())
    assert counts == [
        2
    ], f"Expected exactly 2 calls detected; got: {violations}"

    # One direct call plus one call inside a nested helper — must NOT be flagged.
    nested_ok_file = tmp_path / "synthetic_nested_ok.py"
    nested_ok_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        def _retry():\n"
        "            self.bridge.execute_with_setup(actor_id='retry', bt=None)\n"
        "        return self.bridge.execute_with_setup(actor_id='a', bt=None)\n",
        encoding="utf-8",
    )
    non_violations = _count_multi_execute_violations(nested_ok_file)
    assert not non_violations, (
        "Detector produced a false positive for a nested helper function: "
        f"{non_violations}"
    )
