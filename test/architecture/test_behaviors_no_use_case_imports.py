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
"""Architecture boundary test: behaviors layer must not import from use_cases layer.

``vultron/core/behaviors/`` MUST NOT import from ``vultron/core/use_cases/`` —
neither at module level nor via deferred (local) imports.  The permitted
direction is one-way: use-cases drive BT trees; BT nodes are the implementation
layer of use-cases, not their consumers.

Spec: BTND-04-003

Ratchet pattern
---------------
``KNOWN_VIOLATIONS`` documents every pre-existing violation awaiting
migration.  The test asserts::

    actual_violations == KNOWN_VIOLATIONS

This means:

* **Adding a new violation** causes the test to **fail** immediately.
* **Fixing a violation** also causes the test to **fail** until the resolved
  entry is removed from ``KNOWN_VIOLATIONS``.

Remove entries from ``KNOWN_VIOLATIONS`` one by one as each violation is fixed.
When the set is empty the boundary is completely clean.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]  # test/architecture/ → test/ → repo root

_USE_CASES_MODULE = "vultron.core.use_cases"

_BEHAVIORS_ROOT = REPO_ROOT / "vultron" / "core" / "behaviors"


def _imports_from_use_cases(source_path: Path) -> bool:
    """Return True if *source_path* contains any import from vultron.core.use_cases.

    Detects both top-level and deferred (local) imports, catching violations
    like the former ``from vultron.core.use_cases.received.case._helpers import
    _ensure_reporter_participant`` placed inside ``update()`` method bodies.
    """
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == _USE_CASES_MODULE or module.startswith(
                _USE_CASES_MODULE + "."
            ):
                return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _USE_CASES_MODULE or alias.name.startswith(
                    _USE_CASES_MODULE + "."
                ):
                    return True
    return False


def _collect_violations() -> frozenset[str]:
    """Return repo-relative paths of behaviors files that import from use_cases."""
    violations: set[str] = set()
    for py_file in _BEHAVIORS_ROOT.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        if _imports_from_use_cases(py_file):
            violations.add(py_file.relative_to(REPO_ROOT).as_posix())
    return frozenset(violations)


# ---------------------------------------------------------------------------
# Known pre-existing violations awaiting migration (BTND-04-003).
# Remove entries here one by one as each violation is fixed.
# Issue #1428 tracks the next batch of fixes.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset(
    [
        "vultron/core/behaviors/case/accept_invite_tree.py",
        "vultron/core/behaviors/case/nodes/actor.py",
        "vultron/core/behaviors/case/nodes/announce.py",
        "vultron/core/behaviors/case/nodes/case_participant_received.py",
        "vultron/core/behaviors/case/nodes/case_setup.py",
        "vultron/core/behaviors/case/nodes/conditions.py",
        "vultron/core/behaviors/case/nodes/embargo.py",
        "vultron/core/behaviors/case/nodes/lifecycle.py",
        "vultron/core/behaviors/case/nodes/participant/common.py",
        "vultron/core/behaviors/case/nodes/participant/owner.py",
        "vultron/core/behaviors/case/nodes/participant/participant_add.py",
        "vultron/core/behaviors/case/nodes/update.py",
        "vultron/core/behaviors/case/update_support.py",
        "vultron/core/behaviors/embargo/nodes/lifecycle.py",
        "vultron/core/behaviors/embargo/nodes/proposal.py",
        "vultron/core/behaviors/embargo/nodes/teardown.py",
        "vultron/core/behaviors/note/nodes/creation.py",
        "vultron/core/behaviors/note/nodes/storage.py",
        "vultron/core/behaviors/report/nodes/conditions.py",
        "vultron/core/behaviors/report/nodes/emit.py",
        "vultron/core/behaviors/report/nodes/participant.py",
        "vultron/core/behaviors/report/nodes/rm_transitions.py",
        "vultron/core/behaviors/report/nodes/storage.py",
        "vultron/core/behaviors/sender/nodes/actions.py",
        "vultron/core/behaviors/status/nodes/append.py",
        "vultron/core/behaviors/status/nodes/case_status.py",
        "vultron/core/behaviors/status/nodes/lifecycle.py",
        "vultron/core/behaviors/sync/nodes/chain.py",
        "vultron/core/behaviors/sync/nodes/effects.py",
        "vultron/core/behaviors/sync/nodes/replay.py",
    ]
)


def test_behaviors_does_not_import_use_cases():
    """vultron/core/behaviors/ must not import from vultron/core/use_cases/.

    Spec: BTND-04-003

    See module docstring for the ratchet strategy.
    """
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW violations (behaviors/ must not import from use_cases/):"
        )
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED violations (remove these entries from KNOWN_VIOLATIONS):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)
