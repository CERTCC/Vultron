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
"""Architecture ratchet: BT node update() methods that mutate attributed_to MUST use save_many().

Any BT node ``update()`` that assigns to an ``attributed_to`` field on a
domain object AND also calls ``self.datalayer.save()`` is a violation of
CM-21-004 and BTND-06-008.

The correct pattern is to collect all mutated objects in a list and commit
them atomically via ``self.datalayer.save_many()``.  Using sequential
``self.datalayer.save()`` calls creates a window where partial state (e.g.
zero ``CASE_OWNER`` holders) is observable — violating CM-21-001.

This test uses ``ast.walk`` to detect ``update()`` methods in
``vultron/core/behaviors/`` that simultaneously:

1. Contain an attribute-assignment statement whose target is an
   ``attributed_to`` attribute (``x.attributed_to = ...``).
2. Contain a call to ``self.datalayer.save(...)`` (single-object save).

A ``KNOWN_VIOLATIONS`` ratchet tracks pre-existing sites awaiting
correction.  The set is **exact**: new violations fail the test immediately,
and resolved violations (entries in ``KNOWN_VIOLATIONS`` that no longer
appear in the scan) also fail — prompting the entry to be removed from
``KNOWN_VIOLATIONS``.

See ``AcceptCaseOwnershipTransferNode`` in
``vultron/core/behaviors/case/nodes/ownership_transfer.py`` for the
canonical compliant implementation pattern.

Specs: CM-21-004 (``specs/case-management.yaml``),
BTND-06-008 (``specs/behavior-tree-node-design.yaml``).
AGENTS.md pitfall: "Multi-Object Mutations Touching attributed_to MUST Use
save_many()" in ``vultron/core/AGENTS.md``.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]  # test/architecture/ → test/ → repo root

_BEHAVIORS_ROOT = REPO_ROOT / "vultron" / "core" / "behaviors"


def _walk_own_scope(node: ast.AST):
    """Yield all descendants of *node* without crossing nested function scopes.

    Unlike ``ast.walk``, this generator stops descending when it encounters a
    ``FunctionDef``, ``AsyncFunctionDef``, or ``Lambda`` that is not the root
    *node* itself.  This prevents matches inside inner helper functions or
    lambda bodies defined inside ``update()`` from being counted as direct
    violations.
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(
            child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
        ):
            continue
        yield from _walk_own_scope(child)


def _has_attributed_to_assignment(scope: ast.AST) -> bool:
    """Return True if *scope* contains an assignment to an ``attributed_to`` attribute.

    Detects statements of the form ``x.attributed_to = ...`` or
    ``self.x.attributed_to = ...`` (any depth).  Keyword arguments in
    constructor calls (``attributed_to=...``) are NOT matched because they
    are ``ast.keyword`` nodes, not assignment targets.

    Only attribute nodes in Store context are matched; Load-context occurrences
    (e.g. the inner node in ``obj.attributed_to.sub_field = x``) are skipped.
    Augmented assignments (``obj.attributed_to += ...``) are also detected.
    """
    for node in _walk_own_scope(scope):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for tnode in ast.walk(target):
                    if (
                        isinstance(tnode, ast.Attribute)
                        and tnode.attr == "attributed_to"
                        and isinstance(tnode.ctx, ast.Store)
                    ):
                        return True
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Attribute)
                and node.target.attr == "attributed_to"
                and isinstance(node.target.ctx, ast.Store)
            ):
                return True
        elif isinstance(node, ast.AugAssign):
            if (
                isinstance(node.target, ast.Attribute)
                and node.target.attr == "attributed_to"
            ):
                return True
    return False


def _has_datalayer_save_call(scope: ast.AST) -> bool:
    """Return True if *scope* contains a single-object DataLayer save call.

    Only matches the single-object ``save`` method, not ``save_many``.  BT
    nodes access the DataLayer as ``self.datalayer`` (directly or via a local
    alias ``dl = self.datalayer``).

    Matched forms:
    - ``self.datalayer.save(...)``
    - ``dl.save(...)``  (local variable named ``dl``)
    """
    _DL_RECEIVER_ATTRS: frozenset[str] = frozenset({"datalayer"})
    _DL_LOCAL_NAMES: frozenset[str] = frozenset({"dl"})

    for node in _walk_own_scope(scope):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr != "save":
            continue
        recv = func.value
        # self.datalayer.save(...)
        if (
            isinstance(recv, ast.Attribute)
            and recv.attr in _DL_RECEIVER_ATTRS
            and isinstance(recv.value, ast.Name)
            and recv.value.id == "self"
        ):
            return True
        # dl.save(...) — local alias for self.datalayer
        if isinstance(recv, ast.Name) and recv.id in _DL_LOCAL_NAMES:
            return True
    return False


def _has_attributed_to_with_save_in_update(source_path: Path) -> bool:
    """Return True if *source_path* has an update() that assigns attributed_to
    and also calls self.datalayer.save().
    """
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != "update":
            continue
        if _has_attributed_to_assignment(node) and _has_datalayer_save_call(
            node
        ):
            return True
    return False


def _collect_violations() -> frozenset[str]:
    """Return repo-relative paths of BT node files with the violation pattern."""
    violations: set[str] = set()
    for py_file in _BEHAVIORS_ROOT.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        if _has_attributed_to_with_save_in_update(py_file):
            violations.add(py_file.relative_to(REPO_ROOT).as_posix())
    return frozenset(violations)


# ---------------------------------------------------------------------------
# Known pre-existing violations awaiting correction.
#
# These BT node update() methods assign to attributed_to AND call
# self.datalayer.save() instead of self.datalayer.save_many(), violating
# the atomic-write requirement of CM-21-004 and BTND-06-008.
#
# Remove an entry once that node has been refactored to collect all mutated
# objects and commit them via a single save_many() call.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset()


def test_attributed_to_mutations_use_save_many():
    """BT update() methods assigning attributed_to MUST call save_many(), not save().

    Specs: CM-21-004, BTND-06-008.

    See module docstring for the ratchet strategy.
    """
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW violations — update() assigns to attributed_to and calls"
            " self.datalayer.save(); must use self.datalayer.save_many()"
            " for atomic multi-object commit (CM-21-004, BTND-06-008):"
        )
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED violations — remove these entries from KNOWN_VIOLATIONS:"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)


# ---------------------------------------------------------------------------
# Synthetic detector-validation tests (AC-3)
# ---------------------------------------------------------------------------


def test_detector_catches_attributed_to_with_save(tmp_path: Path) -> None:
    """True-positive: attributed_to assignment + self.datalayer.save() is flagged."""
    violation_file = tmp_path / "synthetic_violation.py"
    violation_file.write_text(
        "class FakeNode:\n"
        "    def update(self):\n"
        "        case.attributed_to = self.new_owner_id\n"
        "        self.datalayer.save(case)\n",
        encoding="utf-8",
    )
    assert _has_attributed_to_with_save_in_update(
        violation_file
    ), "Detector did not flag attributed_to assignment + self.datalayer.save()"


def test_detector_does_not_flag_attributed_to_with_save_many(
    tmp_path: Path,
) -> None:
    """False-positive: attributed_to assignment + save_many() is NOT flagged."""
    clean_file = tmp_path / "synthetic_save_many.py"
    clean_file.write_text(
        "class FakeNode:\n"
        "    def update(self):\n"
        "        case.attributed_to = self.new_owner_id\n"
        "        self.datalayer.save_many([case, participant])\n",
        encoding="utf-8",
    )
    assert not _has_attributed_to_with_save_in_update(
        clean_file
    ), "Detector falsely flagged attributed_to + save_many() as a violation"


def test_detector_does_not_flag_save_without_attributed_to(
    tmp_path: Path,
) -> None:
    """False-positive: self.datalayer.save() without attributed_to mutation is NOT flagged."""
    clean_file = tmp_path / "synthetic_save_only.py"
    clean_file.write_text(
        "class FakeNode:\n"
        "    def update(self):\n"
        "        self.datalayer.save(self.obj)\n",
        encoding="utf-8",
    )
    assert not _has_attributed_to_with_save_in_update(
        clean_file
    ), "Detector falsely flagged save() without attributed_to mutation"


def test_detector_does_not_flag_attributed_to_kwarg_with_save(
    tmp_path: Path,
) -> None:
    """False-positive: attributed_to as constructor kwarg + save() is NOT flagged.

    ``SomeClass(attributed_to=x)`` is a keyword argument, not an attribute
    assignment.  Only ``x.attributed_to = y`` (an Assign/AnnAssign target)
    qualifies as the mutation pattern the ratchet guards against.
    """
    clean_file = tmp_path / "synthetic_kwarg.py"
    clean_file.write_text(
        "class FakeNode:\n"
        "    def update(self):\n"
        "        obj = SomeClass(attributed_to=self.actor_id)\n"
        "        self.datalayer.save(obj)\n",
        encoding="utf-8",
    )
    assert not _has_attributed_to_with_save_in_update(
        clean_file
    ), "Detector falsely flagged attributed_to constructor kwarg + save() as a violation"


def test_detector_does_not_flag_violation_in_inner_function(
    tmp_path: Path,
) -> None:
    """Violations inside a nested function defined in update() are NOT flagged.

    Only the direct (own-scope) body of update() is inspected; inner scopes
    are excluded by _walk_own_scope.
    """
    clean_file = tmp_path / "synthetic_inner_fn.py"
    clean_file.write_text(
        "class FakeNode:\n"
        "    def update(self):\n"
        "        def _inner():\n"
        "            case.attributed_to = owner_id\n"
        "            self.datalayer.save(case)\n"
        "        _inner()\n",
        encoding="utf-8",
    )
    assert not _has_attributed_to_with_save_in_update(
        clean_file
    ), "Detector produced false positive for violation inside nested function"


def test_detector_catches_local_dl_rebind_with_save(tmp_path: Path) -> None:
    """True-positive: attributed_to assignment + ``dl = self.datalayer; dl.save()`` is flagged.

    BT nodes sometimes alias ``dl = self.datalayer`` before calling ``dl.save()``.
    The detector must catch this rebind pattern as well as the direct form.
    """
    violation_file = tmp_path / "synthetic_rebind.py"
    violation_file.write_text(
        "class FakeNode:\n"
        "    def update(self):\n"
        "        dl = self.datalayer\n"
        "        case.attributed_to = self.new_owner_id\n"
        "        dl.save(case)\n",
        encoding="utf-8",
    )
    assert _has_attributed_to_with_save_in_update(
        violation_file
    ), "Detector did not flag attributed_to + dl.save() via local rebind"


def test_detector_does_not_flag_subfield_assignment(tmp_path: Path) -> None:
    """False-positive: assigning to a sub-field of attributed_to is NOT flagged.

    In ``obj.attributed_to.sub_field = x`` the ``attributed_to`` attribute node
    appears in the Load context (it is read, not stored).  Only the outer
    ``sub_field`` node has Store context.  The detector must not match this.
    """
    clean_file = tmp_path / "synthetic_subfield.py"
    clean_file.write_text(
        "class FakeNode:\n"
        "    def update(self):\n"
        "        obj.attributed_to.sub_field = new_value\n"
        "        self.datalayer.save(obj)\n",
        encoding="utf-8",
    )
    assert not _has_attributed_to_with_save_in_update(
        clean_file
    ), "Detector falsely flagged sub-field assignment on attributed_to as a violation"


def test_detector_catches_augmented_assignment_to_attributed_to(
    tmp_path: Path,
) -> None:
    """True-positive: ``obj.attributed_to += [extra]`` + save() is flagged.

    Augmented assignments (AugAssign) also mutate attributed_to and violate the
    atomic-write requirement of CM-21-004.
    """
    violation_file = tmp_path / "synthetic_augassign.py"
    violation_file.write_text(
        "class FakeNode:\n"
        "    def update(self):\n"
        "        case.attributed_to += [self.new_owner_id]\n"
        "        self.datalayer.save(case)\n",
        encoding="utf-8",
    )
    assert _has_attributed_to_with_save_in_update(
        violation_file
    ), "Detector did not flag augmented assignment to attributed_to + save()"
