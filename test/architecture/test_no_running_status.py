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
"""Architecture ratchet: no node under vultron/ returns Status.RUNNING.

Vultron's execution model has nowhere to suspend a behavior tree: the
``BTBridge`` busy-loops on a root ``RUNNING`` until it exhausts
``max_iterations``, then fails opaquely (ADR-0080). Every Vultron BT node MUST
answer synchronously with ``SUCCESS`` or ``FAILURE`` — no node returns
``RUNNING`` (BT-18-011, the codebase-wide invariant).

This static check complements the runtime guard
(:class:`~vultron.core.behaviors.call_out.guard.SynchronousCallOut`): the guard
catches call-out backends injected from outside the repo, while this ratchet
catches any in-repo node authored to return ``RUNNING``.

The detector uses ``ast`` to find ``return`` statements whose value references
the py_trees ``Status.RUNNING`` enum member anywhere in the returned expression
— catching ``return Status.RUNNING``, ``return py_trees.common.Status.RUNNING``,
and less-obvious forms such as ``return random.choice((Status.SUCCESS,
Status.RUNNING))``.

Two deliberate exclusions:

- The legacy simulator (``vultron/bt/``) uses a *different* enum,
  ``NodeStatus.RUNNING``, with its own continuous-tick engine where RUNNING is
  legitimate. The detector keys on the enum name ``Status``, so
  ``NodeStatus.RUNNING`` is not flagged.
- A *comparison* such as ``if status == Status.RUNNING`` is not a return of
  RUNNING and is not flagged — only RUNNING appearing inside a ``return`` value
  is.

Spec: BT-18-011 (``specs/behavior-tree-integration.yaml``).
ADR: ADR-0080.
"""

import ast
from pathlib import Path
from test.architecture import _corpus

_VULTRON_ROOT = _corpus.REPO_ROOT / "vultron"


def _enum_name(value: ast.expr) -> str | None:
    """Return the name of the enum an attribute is accessed on.

    ``Status.RUNNING`` -> ``"Status"`` (``value`` is a ``Name``);
    ``common.Status.RUNNING`` -> ``"Status"`` (``value`` is an ``Attribute``).
    """
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    return None


def _references_status_running(node: ast.AST) -> bool:
    """True if *node* is ``<...>.Status.RUNNING`` (py_trees, not NodeStatus)."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "RUNNING"
        and _enum_name(node.value) == "Status"
    )


def _returns_running(node: ast.AST) -> bool:
    """True if *node* is a ``return`` whose value references ``Status.RUNNING``."""
    if not isinstance(node, ast.Return) or node.value is None:
        return False
    return any(
        _references_status_running(inner) for inner in ast.walk(node.value)
    )


def _tree_returns_running(tree: ast.AST) -> bool:
    return any(_returns_running(node) for node in ast.walk(tree))


def _file_returns_running(source_path: Path) -> bool:
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = _corpus.parse_inline(source, filename=str(source_path))
    except (OSError, SyntaxError):
        return False
    return _tree_returns_running(tree)


def _collect_violations() -> frozenset[str]:
    """Repo-relative paths of vultron/ files that ``return ...RUNNING``."""
    violations: set[str] = set()
    for py_file, tree in _corpus.files_mentioning(
        "RUNNING", under=_VULTRON_ROOT
    ):
        if _tree_returns_running(tree):
            violations.add(py_file.relative_to(_corpus.REPO_ROOT).as_posix())
    return frozenset(violations)


# ---------------------------------------------------------------------------
# No node under vultron/ returns Status.RUNNING (BT-18-011).  The set is exact:
# the invariant is that this stays empty.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset()


def test_no_node_returns_running():
    """No file under vultron/ contains ``return Status.RUNNING`` (BT-18-011)."""
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW violations (a node under vultron/ returns Status.RUNNING — a "
            "call-out point / BT node MUST answer synchronously with SUCCESS "
            "or FAILURE, BT-18-011 / ADR-0080):"
        )
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED entries (remove these from KNOWN_VIOLATIONS):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)


# ---------------------------------------------------------------------------
# Synthetic detector-validation tests
# ---------------------------------------------------------------------------


def test_detector_catches_return_status_running(tmp_path: Path) -> None:
    """Confirm the scanner flags ``return Status.RUNNING`` in a node."""
    f = tmp_path / "synthetic_running.py"
    f.write_text(
        "from py_trees.common import Status\n"
        "class FakeNode:\n"
        "    def update(self):\n"
        "        return Status.RUNNING\n",
        encoding="utf-8",
    )
    assert _file_returns_running(f)


def test_detector_catches_fully_qualified_running(tmp_path: Path) -> None:
    """Confirm the scanner flags ``return py_trees.common.Status.RUNNING``."""
    f = tmp_path / "synthetic_running_fq.py"
    f.write_text(
        "import py_trees\n"
        "class FakeNode:\n"
        "    def update(self):\n"
        "        return py_trees.common.Status.RUNNING\n",
        encoding="utf-8",
    )
    assert _file_returns_running(f)


def test_detector_does_not_flag_running_comparison(tmp_path: Path) -> None:
    """A comparison against Status.RUNNING (not a return) must not be flagged."""
    f = tmp_path / "synthetic_compare.py"
    f.write_text(
        "from py_trees.common import Status\n"
        "class FakeNode:\n"
        "    def update(self):\n"
        "        if self.status == Status.RUNNING:\n"
        "            return Status.SUCCESS\n"
        "        return Status.FAILURE\n",
        encoding="utf-8",
    )
    assert not _file_returns_running(f)


def test_detector_does_not_flag_success_or_failure(tmp_path: Path) -> None:
    """Returning SUCCESS / FAILURE must not be flagged."""
    f = tmp_path / "synthetic_ok.py"
    f.write_text(
        "from py_trees.common import Status\n"
        "class FakeNode:\n"
        "    def update(self):\n"
        "        return Status.SUCCESS\n",
        encoding="utf-8",
    )
    assert not _file_returns_running(f)


def test_detector_catches_running_inside_return_expression(
    tmp_path: Path,
) -> None:
    """RUNNING inside a return expression (e.g. random.choice) is flagged."""
    f = tmp_path / "synthetic_running_choice.py"
    f.write_text(
        "import random\n"
        "from py_trees.common import Status\n"
        "class FakeNode:\n"
        "    def update(self):\n"
        "        return random.choice((Status.SUCCESS, Status.RUNNING))\n",
        encoding="utf-8",
    )
    assert _file_returns_running(f)


def test_detector_does_not_flag_legacy_node_status_running(
    tmp_path: Path,
) -> None:
    """The legacy simulator's NodeStatus.RUNNING is a different engine; skip it."""
    f = tmp_path / "synthetic_node_status.py"
    f.write_text(
        "from vultron.bt.base.node_status import NodeStatus\n"
        "class FakeSimNode:\n"
        "    def _tick(self):\n"
        "        return NodeStatus.RUNNING\n",
        encoding="utf-8",
    )
    assert not _file_returns_running(f)
