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
"""Architecture boundary test: core layer must not import from adapters layer.

``vultron/core/`` is the innermost layer in the hexagonal architecture.  It
MUST NOT import from ``vultron/adapters/`` — neither at module level nor via
deferred (local) imports.  Adapters are the outermost layer and depend on
core, not the other way around.

Spec: ARCH-01-001

Ratchet pattern
---------------
``KNOWN_VIOLATIONS`` documents every pre-existing violation awaiting
migration.  The test asserts::

    actual_violations == KNOWN_VIOLATIONS

This means:

* **Adding a new violation** causes the test to **fail** immediately.
* **Fixing a violation** also causes the test to **fail** until the resolved
  entry is removed from ``KNOWN_VIOLATIONS``.

Remove entries from ``KNOWN_VIOLATIONS`` one by one as each violation is
fixed.  When the set is empty the boundary is completely clean.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]  # test/architecture/ → test/ → repo root

_ADAPTERS_MODULE = "vultron.adapters"
_ADAPTERS_PATH = "vultron/adapters"

_CORE_ROOT = REPO_ROOT / "vultron" / "core"


def _imports_from_adapters(source_path: Path) -> bool:
    """Return True if *source_path* contains any import from vultron.adapters.

    Detects both top-level and deferred (local) imports, catching violations
    like ``from vultron.adapters.driven.sync_activity_adapter import ...``
    placed inside a function body.
    """
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == _ADAPTERS_MODULE or module.startswith(
                _ADAPTERS_MODULE + "."
            ):
                return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _ADAPTERS_MODULE or alias.name.startswith(
                    _ADAPTERS_MODULE + "."
                ):
                    return True
    return False


def _collect_violations() -> frozenset[str]:
    """Return repo-relative paths of core files that import from adapters."""
    violations: set[str] = set()
    for py_file in _CORE_ROOT.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        if _imports_from_adapters(py_file):
            violations.add(py_file.relative_to(REPO_ROOT).as_posix())
    return frozenset(violations)


# ---------------------------------------------------------------------------
# Known pre-existing violations awaiting migration.
# All violations have been resolved; this set is intentionally empty.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset()


def test_core_does_not_import_adapters():
    """vultron/core/ must not import from vultron/adapters/ at any code path.

    Spec: ARCH-01-001

    See module docstring for the ratchet strategy.
    """
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW violations (core must not import from adapters):"
        )
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED violations (remove these entries from KNOWN_VIOLATIONS):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)
