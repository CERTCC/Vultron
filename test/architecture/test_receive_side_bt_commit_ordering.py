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

"""
Structural test: receive-side BT tree factories must not call
``create_guarded_commit_case_ledger_entry_tree`` directly.

All tree factory files under ``vultron/core/behaviors/`` that build
receive-side BTs must use ``create_receive_activity_tree`` instead, which
enforces the correct ledger-commit-before-effects ordering (CLP-10-006).

Only ``vultron/core/behaviors/case/nodes/lifecycle.py`` — which *defines*
``create_guarded_commit_case_ledger_entry_tree`` and is called by
``create_receive_activity_tree`` — is exempt from this rule.

This test is a ratchet: if a new violation is introduced, the test fails
immediately rather than silently accumulating debt.
"""

import ast
import os
from pathlib import Path

import pytest

# Exempt files: may contain direct calls (definition site only).
EXEMPT_FILES = {
    "vultron/core/behaviors/case/nodes/lifecycle.py",
}

BEHAVIORS_ROOT = Path(__file__).parents[2] / "vultron" / "core" / "behaviors"
FORBIDDEN_CALL = "create_guarded_commit_case_ledger_entry_tree"


def _is_forbidden_call(node: ast.AST) -> bool:
    """Return True if node is a Call to the forbidden function name."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id == FORBIDDEN_CALL:
        return True
    if isinstance(func, ast.Attribute) and func.attr == FORBIDDEN_CALL:
        return True
    return False


def _find_violations() -> list[tuple[str, int]]:
    """Return (relative_path, line_no) for each forbidden call outside exempt files."""
    violations: list[tuple[str, int]] = []
    repo_root = Path(__file__).parents[2]

    for dirpath, _, filenames in os.walk(BEHAVIORS_ROOT):
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            full_path = Path(dirpath) / filename
            rel_path = str(full_path.relative_to(repo_root))

            if rel_path in EXEMPT_FILES:
                continue

            source = full_path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source, filename=rel_path)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if _is_forbidden_call(node):
                    assert isinstance(node, ast.Call)
                    violations.append((rel_path, node.lineno))

    return violations


def test_no_direct_calls_to_guarded_commit_outside_lifecycle() -> None:
    """No tree factory outside lifecycle.py may call create_guarded_commit_case_ledger_entry_tree.

    All receive-side tree factories must use create_receive_activity_tree,
    which enforces commit-before-effects ordering (CLP-10-006).
    """
    violations = _find_violations()
    if violations:
        lines = "\n".join(
            f"  {path}:{line_no}" for path, line_no in violations
        )
        pytest.fail(
            f"Found {len(violations)} direct call(s) to"
            f" `{FORBIDDEN_CALL}` outside the exempt lifecycle module.\n"
            f"Use `create_receive_activity_tree` instead (CLP-10-006):\n"
            f"{lines}"
        )
