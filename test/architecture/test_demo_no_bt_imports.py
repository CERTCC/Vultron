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
"""Architecture boundary test: demo layer must not import the legacy simulator.

``vultron/demo/`` demonstrates the **production** protocol (API server, core,
and wire layers).  It MUST NOT import from the frozen legacy ``vultron/bt/``
custom-engine simulator — neither at module level nor via deferred (local)
imports.

Spec: ARCH-01-006 (refines ARCH-01-001)

The sole permitted exception is the unified demo CLI aggregator
(``vultron/demo/cli.py``, mandated by DC-01-001), which surfaces the standalone
``vultron/bt/``-based behaviour-tree demos (pacman, robot, cvd) as a
``vultrabot`` sub-group.

Ratchet pattern
---------------
``KNOWN_VIOLATIONS`` documents every permitted/pending violation.  The test
asserts::

    actual_violations == KNOWN_VIOLATIONS

This means:

* **Adding a new violation** causes the test to **fail** immediately.
* **Removing the documented exception** (or fixing it) also causes the test to
  **fail** until the resolved entry is removed from ``KNOWN_VIOLATIONS``.

Follows the ARCH-18 bidirectional-equality pattern used by
``test/architecture/test_core_no_wire_imports.py``.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]  # test/architecture/ → test/ → repo root

_BT_MODULE = "vultron.bt"

_DEMO_ROOT = REPO_ROOT / "vultron" / "demo"


def _imports_from_bt(source_path: Path) -> bool:
    """Return True if *source_path* contains any import from vultron.bt.

    Detects both top-level and deferred (local) imports, catching violations
    like ``import vultron.bt.base.demo.pacman`` placed inside a function body.
    """
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == _BT_MODULE or module.startswith(_BT_MODULE + "."):
                return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _BT_MODULE or alias.name.startswith(
                    _BT_MODULE + "."
                ):
                    return True
    return False


def _collect_violations() -> frozenset[str]:
    """Return repo-relative paths of demo files that import from vultron.bt."""
    violations: set[str] = set()
    for py_file in _DEMO_ROOT.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        if _imports_from_bt(py_file):
            violations.add(py_file.relative_to(REPO_ROOT).as_posix())
    return frozenset(violations)


# ---------------------------------------------------------------------------
# Known / permitted violations.
# Only the unified demo CLI aggregator may import the standalone bt-tree demos
# (pacman, robot, cvd) to surface them as the ``vultrabot`` sub-group. This is
# the single documented bridge to the legacy simulator (ARCH-01-006, DC-01-001).
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset({"vultron/demo/cli.py"})


def test_demo_does_not_import_bt():
    """vultron/demo/ must not import from vultron/bt/ except the CLI aggregator.

    Spec: ARCH-01-006

    See module docstring for the ratchet strategy.
    """
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW violations (demo must not import from the legacy bt simulator):"
        )
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED violations (remove these entries from KNOWN_VIOLATIONS):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)
