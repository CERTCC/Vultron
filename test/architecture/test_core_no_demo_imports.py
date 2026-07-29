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
"""Architecture boundary test: core layer must not import from the demo layer.

``vultron/core/`` is the innermost layer in the hexagonal architecture.  It
MUST NOT import from ``vultron/demo/`` — neither at module level nor via
deferred (local) imports.  ``vultron/demo/`` (including the ``fuzzer``
simulation package) is a driving/simulation layer that depends on core, not
the other way around (BT-16-001: simulation artifacts stay out of core).

This guards the ADR-0025 corrected layering: the call-out point seam
(``CallOutBackendFactory`` Protocol), the deterministic ``AlwaysSucceed`` /
``AlwaysFail`` nodes, and the ``<DOMAIN>_DETERMINISTIC`` bundles all live in
``vultron/core/behaviors/call_out/``; only the probabilistic ``WeightedBehavior``
nodes and ``<DOMAIN>_STOCHASTIC`` bundles remain in ``vultron/demo/fuzzer/`` and
are injected explicitly via ``call_out=``.

Spec: ARCH-01-001, BT-16-001

Ratchet pattern
---------------
``KNOWN_VIOLATIONS`` documents every pre-existing violation awaiting
migration.  The test asserts::

    actual_violations == KNOWN_VIOLATIONS

This means:

* **Adding a new violation** causes the test to **fail** immediately.
* **Fixing a violation** also causes the test to **fail** until the resolved
  entry is removed from ``KNOWN_VIOLATIONS``.

The set is empty: the core→demo boundary is completely clean.  Keep it that way.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]  # test/architecture/ → test/ → repo root

_DEMO_MODULE = "vultron.demo"

_CORE_ROOT = REPO_ROOT / "vultron" / "core"


def _imports_from_demo(source_path: Path) -> bool:
    """Return True if *source_path* contains any import from vultron.demo.

    Detects both top-level and deferred (local) imports, catching violations
    like ``from vultron.demo.fuzzer.bundles.validation import ...`` placed
    inside a function body.
    """
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == _DEMO_MODULE or module.startswith(_DEMO_MODULE + "."):
                return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _DEMO_MODULE or alias.name.startswith(
                    _DEMO_MODULE + "."
                ):
                    return True
    return False


def _collect_violations() -> frozenset[str]:
    """Return repo-relative paths of core files that import from demo."""
    violations: set[str] = set()
    for py_file in _CORE_ROOT.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        if _imports_from_demo(py_file):
            violations.add(py_file.relative_to(REPO_ROOT).as_posix())
    return frozenset(violations)


# ---------------------------------------------------------------------------
# Known pre-existing violations awaiting migration.
# The core→demo boundary is clean, so this set is empty.  Do not add entries:
# core code needing a call-out backend default must use the core-owned
# ``vultron.core.behaviors.call_out`` package, never ``vultron.demo``.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset()


def test_core_does_not_import_demo():
    """vultron/core/ must not import from vultron/demo/ at any code path.

    Spec: ARCH-01-001, BT-16-001

    See module docstring for the ratchet strategy.
    """
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append("NEW violations (core must not import from demo):")
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED violations (remove these entries from KNOWN_VIOLATIONS):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)
