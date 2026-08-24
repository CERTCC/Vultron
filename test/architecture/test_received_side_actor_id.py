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
"""Architecture invariant: received-side execute_with_setup must use receiving_actor_id.

Spec BT-17-006 (MUST): any received-side use case that calls
``execute_with_setup`` MUST pass ``actor_id=request.receiving_actor_id``
(or a local variable derived from it), never ``actor_id=request.actor_id``
(the sender).  Passing the sender ID scopes the DataLayer and GuardedCommit
to the wrong actor, silently attributing ledger entries and state transitions
to the remote peer.

Issue: #2338
"""

import ast
from pathlib import Path

from test.architecture import _corpus

_RECEIVED_ROOT = (
    _corpus.REPO_ROOT / "vultron" / "core" / "use_cases" / "received"
)


def _is_execute_with_setup_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute) and func.attr == "execute_with_setup"
    ) or (isinstance(func, ast.Name) and func.id == "execute_with_setup")


def _walk_own_scope(node: ast.AST):
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        yield from _walk_own_scope(child)


def _is_request_actor_id(node: ast.expr) -> bool:
    """Return True for the AST node ``request.actor_id``."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "actor_id"
        and isinstance(node.value, ast.Name)
        and node.value.id == "request"
    )


def _label(source_path: Path) -> str:
    try:
        return source_path.relative_to(_corpus.REPO_ROOT).as_posix()
    except ValueError:
        return str(source_path)


def _violations_in_execute(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    label: str,
) -> list[str]:
    """Return 'label:lineno' for every execute_with_setup that passes request.actor_id."""
    results: list[str] = []
    for child in _walk_own_scope(func):
        if not _is_execute_with_setup_call(child):
            continue
        assert isinstance(child, ast.Call)
        for kw in child.keywords:
            if kw.arg == "actor_id" and _is_request_actor_id(kw.value):
                results.append(f"{label}:{child.lineno}")
    return results


def _collect_violations_from_tree(tree: ast.AST, label: str) -> list[str]:
    """Return 'file:lineno' entries where execute_with_setup passes request.actor_id."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != "execute":
            continue
        violations.extend(_violations_in_execute(node, label))
    return violations


def _collect_violations(source_path: Path) -> list[str]:
    """Scan a single file (including tmp_path synthetic files not in corpus)."""
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = _corpus.parse_inline(source, filename=str(source_path))
    except (OSError, SyntaxError):
        return []
    return _collect_violations_from_tree(tree, _label(source_path))


def test_received_side_execute_with_setup_never_passes_request_actor_id():
    """No received-side execute() may pass actor_id=request.actor_id to execute_with_setup.

    Spec BT-17-006. Issue #2338.
    """
    all_violations: list[str] = []
    for py_file, tree in _corpus.files_mentioning(
        "execute_with_setup", under=_RECEIVED_ROOT
    ):
        all_violations.extend(
            _collect_violations_from_tree(tree, _label(py_file))
        )

    assert not all_violations, (
        "received-side execute() calls pass actor_id=request.actor_id"
        " (should use request.receiving_actor_id — BT-17-006, issue #2338):\n"
        + "\n".join(f"  {v}" for v in sorted(all_violations))
    )


def test_detector_catches_synthetic_violation(tmp_path: Path) -> None:
    """Confirm the detector flags a synthetic request.actor_id violation."""
    violation_file = tmp_path / "synthetic_bad.py"
    violation_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        bridge.execute_with_setup(tree=t, actor_id=request.actor_id)\n",
        encoding="utf-8",
    )
    violations = _collect_violations(violation_file)
    assert violations, "Detector did not flag the synthetic violation"

    ok_file = tmp_path / "synthetic_ok.py"
    ok_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        receiving_actor_id = request.receiving_actor_id\n"
        "        bridge.execute_with_setup(tree=t, actor_id=receiving_actor_id)\n",
        encoding="utf-8",
    )
    assert not _collect_violations(
        ok_file
    ), "Detector produced a false positive for receiving_actor_id usage"

    ok_inline_file = tmp_path / "synthetic_ok_inline.py"
    ok_inline_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        bridge.execute_with_setup(\n"
        "            tree=t,\n"
        "            actor_id=request.receiving_actor_id\n"
        "                if request.receiving_actor_id is not None\n"
        "                else request.actor_id,\n"
        "        )\n",
        encoding="utf-8",
    )
    assert not _collect_violations(
        ok_inline_file
    ), "Detector produced a false positive for defensive inline form"
