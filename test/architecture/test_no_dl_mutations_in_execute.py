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
"""Architecture ratchet: no direct DataLayer mutations in execute() methods.

Each ``execute()`` method in ``vultron/core/use_cases/`` MUST delegate all
DataLayer mutations (``save``, ``create``, ``update``, ``delete``) to a BT
leaf node via ``BTBridge.execute_with_setup()``.  Direct calls like
``self._dl.save(...)`` inside ``execute()`` bypass the BT audit trail,
skip the hash-chained ledger-commit path, and constitute protocol-significant
behavior outside the tree — the exact anti-pattern BT-06-001 and BT-15-001
prohibit.

This test uses ``ast.walk`` to detect mutation calls whose receiver is
``self._dl``, ``self.dl``, or a local variable named ``dl``, and whose
method name is one of ``save``, ``create``, ``update``, or ``delete``.

A ``KNOWN_VIOLATIONS`` ratchet tracks pre-existing sites awaiting migration.
The set is **exact**: new violations fail the test immediately, and resolved
violations (entries in ``KNOWN_VIOLATIONS`` that no longer appear in the scan)
also fail — prompting the entry to be removed from ``KNOWN_VIOLATIONS``.

Spec: CLP-10-005 (``specs/case-ledger-processing.yaml``).
BT specs: BT-06-001, BT-15-001 (``specs/behavior-tree-integration.yaml``).
AGENTS.md pitfall: "Direct DataLayer Mutations in execute() Are Not Caught by
the Import-Based Ratchet".
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]  # test/architecture/ → test/ → repo root

_USE_CASES_ROOT = REPO_ROOT / "vultron" / "core" / "use_cases"

_DL_MUTATION_METHODS: frozenset[str] = frozenset(
    {"save", "create", "update", "delete"}
)
_DL_RECEIVER_ATTRS: frozenset[str] = frozenset({"_dl", "dl"})


def _is_dl_mutation_call(node: ast.AST) -> bool:
    """Return True if *node* is a DataLayer mutation call expression.

    Detects:
    - ``self._dl.METHOD(...)``
    - ``self.dl.METHOD(...)``
    - ``dl.METHOD(...)``  (local variable named ``dl``)

    where METHOD is one of ``save``, ``create``, ``update``, ``delete``.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr not in _DL_MUTATION_METHODS:
        return False
    recv = func.value
    # self._dl.METHOD or self.dl.METHOD
    if (
        isinstance(recv, ast.Attribute)
        and recv.attr in _DL_RECEIVER_ATTRS
        and isinstance(recv.value, ast.Name)
        and recv.value.id == "self"
    ):
        return True
    # dl.METHOD (local variable)
    if isinstance(recv, ast.Name) and recv.id in _DL_RECEIVER_ATTRS:
        return True
    return False


def _walk_own_scope(node: ast.AST):
    """Yield all descendants of *node* without crossing nested function scopes.

    Unlike ``ast.walk``, this generator stops descending when it encounters a
    ``FunctionDef``, ``AsyncFunctionDef``, or ``Lambda`` that is not the root
    *node* itself.  This prevents mutation calls inside inner helper functions
    or lambda bodies defined inside ``execute()`` from being counted as direct
    violations of ``execute()``.
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(
            child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
        ):
            continue
        yield from _walk_own_scope(child)


def _has_dl_mutation_in_execute(source_path: Path) -> bool:
    """Return True if *source_path* contains an execute() method with a direct
    DataLayer mutation call in its own scope (excluding inner functions).
    """
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != "execute":
            continue
        for child in _walk_own_scope(node):
            if _is_dl_mutation_call(child):
                return True
    return False


def _collect_violations() -> frozenset[str]:
    """Return repo-relative paths of use-case files with DL mutations in execute()."""
    violations: set[str] = set()
    for py_file in _USE_CASES_ROOT.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        if _has_dl_mutation_in_execute(py_file):
            violations.add(py_file.relative_to(REPO_ROOT).as_posix())
    return frozenset(violations)


# ---------------------------------------------------------------------------
# Known pre-existing violations awaiting migration to BT leaf nodes.
#
# These files call self._dl.save/create/update/delete directly inside
# their execute() methods, bypassing the BT audit trail and hash-chained
# ledger-commit path (BT-06-001, BT-15-001, CLP-10-005).
#
# Remove an entry once that file's execute() has been refactored to
# delegate all DataLayer mutations via BTBridge.execute_with_setup().
# Migration tracked in issue #1076.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset(
    {
        "vultron/core/use_cases/received/actor/announce.py",
        "vultron/core/use_cases/received/actor/ownership.py",
        "vultron/core/use_cases/received/case/lifecycle.py",
        "vultron/core/use_cases/received/case_participant.py",
        "vultron/core/use_cases/received/note.py",
        "vultron/core/use_cases/received/unknown.py",
    }
)


def test_no_dl_mutations_in_execute():
    """execute() methods in use_cases/ must not call DataLayer mutations directly.

    Spec: CLP-10-005. BT specs: BT-06-001, BT-15-001.

    See module docstring for the ratchet strategy.
    """
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW violations (execute() must not call self._dl.save/create/"
            "update/delete directly — delegate to a BT leaf node instead,"
            " CLP-10-005 / BT-15-001):"
        )
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED violations (remove these entries from KNOWN_VIOLATIONS"
            " — migration #1076 complete for these files):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)


# ---------------------------------------------------------------------------
# Synthetic detector-validation tests
# ---------------------------------------------------------------------------


def test_detector_catches_self_dl_save_in_execute(tmp_path: Path) -> None:
    """Confirm the scanner flags self._dl.save() directly in execute()."""
    violation_file = tmp_path / "synthetic_violation.py"
    violation_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        self._dl.save(self._obj)\n",
        encoding="utf-8",
    )
    assert _has_dl_mutation_in_execute(
        violation_file
    ), "Detector did not flag self._dl.save() in execute()"


def test_detector_catches_all_mutation_methods(tmp_path: Path) -> None:
    """Confirm the scanner flags all four mutation methods."""
    for method in ("save", "create", "update", "delete"):
        f = tmp_path / f"synthetic_{method}.py"
        f.write_text(
            "class FakeUseCase:\n"
            "    def execute(self):\n"
            f"        self._dl.{method}(self._obj)\n",
            encoding="utf-8",
        )
        assert _has_dl_mutation_in_execute(
            f
        ), f"Detector did not flag self._dl.{method}() in execute()"


def test_detector_does_not_flag_reads(tmp_path: Path) -> None:
    """Read-only DataLayer calls (read, list, etc.) must not be flagged."""
    clean_file = tmp_path / "synthetic_read_only.py"
    clean_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        obj = self._dl.read(self._id)\n"
        "        items = self._dl.list()\n",
        encoding="utf-8",
    )
    assert not _has_dl_mutation_in_execute(
        clean_file
    ), "Detector falsely flagged read-only DataLayer calls"


def test_detector_does_not_flag_mutations_in_helper_methods(
    tmp_path: Path,
) -> None:
    """Mutations inside helper methods (not execute()) must not be flagged."""
    clean_file = tmp_path / "synthetic_helper_mutation.py"
    clean_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        self._persist()\n"
        "    def _persist(self):\n"
        "        self._dl.save(self._obj)\n",
        encoding="utf-8",
    )
    assert not _has_dl_mutation_in_execute(
        clean_file
    ), "Detector falsely flagged a mutation inside a non-execute helper method"


def test_detector_does_not_flag_mutations_in_inner_function(
    tmp_path: Path,
) -> None:
    """Mutations inside a nested function defined in execute() must not be flagged.

    Only direct (own-scope) calls inside execute() are violations; calls
    inside inner helpers are excluded by _walk_own_scope.
    """
    clean_file = tmp_path / "synthetic_inner_fn.py"
    clean_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        def _inner():\n"
        "            self._dl.save(self._obj)\n"
        "        _inner()\n",
        encoding="utf-8",
    )
    assert not _has_dl_mutation_in_execute(
        clean_file
    ), "Detector produced false positive for mutation inside nested function"


def test_detector_does_not_flag_mutations_in_lambda(tmp_path: Path) -> None:
    """Mutations inside a lambda defined in execute() must not be flagged.

    ``ast.Lambda`` is a nested scope just like ``FunctionDef``; the mutation
    belongs to the lambda's body, not to ``execute()`` directly.
    """
    clean_file = tmp_path / "synthetic_lambda.py"
    clean_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        fn = lambda: self._dl.save(self._obj)\n"
        "        fn()\n",
        encoding="utf-8",
    )
    assert not _has_dl_mutation_in_execute(
        clean_file
    ), "Detector produced false positive for mutation inside lambda"


def test_detector_catches_local_dl_variable(tmp_path: Path) -> None:
    """Confirm the scanner flags dl.save() via a local variable named dl."""
    violation_file = tmp_path / "synthetic_local_dl.py"
    violation_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        dl = self._dl\n"
        "        dl.save(self._obj)\n",
        encoding="utf-8",
    )
    assert _has_dl_mutation_in_execute(
        violation_file
    ), "Detector did not flag dl.save() via local dl variable"
