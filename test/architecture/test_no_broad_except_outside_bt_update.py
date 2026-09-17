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
"""Architecture ratchet: no broad ``except`` outside a BT node's ``update()``.

CS-23-001 forbids a blanket ``except Exception`` (or a bare ``except:``) around
domain logic in ``vultron/``: an exception handler MUST catch the narrowest
concrete type it can meaningfully handle so that an unexpected error surfaces
loudly instead of being silently absorbed.  In this codebase an undocumented
broad catch is more likely to be masking a defect than handling a real case
(CONCERN-3295; witnesses #3217 and #3192).

The one sanctioned broad-catch boundary is a behavior-tree node's ``update()``
method, where converting an unexpected error into ``Status.FAILURE`` is the
documented node contract (BT-HELPER-01).  This ratchet enforces the rule for
``vultron/core/behaviors/``: it fails on any ``except Exception``/bare ``except``
whose nearest enclosing function is not named ``update``.

Genuine framework/execution boundaries (the ``BTBridge`` execution boundary in
``bridge.py``; the inbox orchestrator's raw py_trees tick loop; boot-recovery
persistence; the SYNC-12-001 write-fails-the-effect boundary) are enumerated in
``_DECLARED_EXCLUSIONS`` with one reason per entry and an exact broad-catch count.
The assertion is an exact match, so the list can only shrink: a new broad catch
in an already-listed file fails the test (the count grew), and a broad catch in
any other file fails immediately.

Spec: CS-23-001 (``specs/code-style.yaml``), refining ARCH-15-002.
See ``notes/domain-validation.md`` § "Broad ``except Exception`` Is a Masking
Smell" and ``notes/architecture-ratchet-corpus.md`` for the corpus pattern.
"""

import ast

from test.architecture import _corpus

_BEHAVIORS_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"

_SANCTIONED_METHOD = "update"


def _is_broad_except(handler: ast.ExceptHandler) -> bool:
    """Return True if *handler* is a blanket catch (``except Exception`` or bare).

    Detects:
    - ``except:``                         (bare — ``handler.type is None``)
    - ``except Exception:``               (``Name`` id == "Exception")
    - ``except (Exception, ...):``        (a tuple that includes ``Exception``)
    """
    exc_type = handler.type
    if exc_type is None:
        return True
    if isinstance(exc_type, ast.Name) and exc_type.id == "Exception":
        return True
    if isinstance(exc_type, ast.Tuple):
        return any(
            isinstance(elt, ast.Name) and elt.id == "Exception"
            for elt in exc_type.elts
        )
    return False


def _count_broad_excepts_outside_update(tree: ast.AST) -> int:
    """Count broad ``except`` handlers whose nearest enclosing def is not update().

    A handler directly inside a method named ``update`` is exempt (the BT node
    contract).  A handler inside a nested helper defined *within* ``update`` is
    NOT exempt: its nearest enclosing function is the helper, not ``update``.
    """
    count = 0

    def visit(node: ast.AST, enclosing_is_update: bool) -> None:
        nonlocal count
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name == _SANCTIONED_METHOD)
            else:
                if isinstance(child, ast.ExceptHandler) and _is_broad_except(
                    child
                ):
                    if not enclosing_is_update:
                        count += 1
                visit(child, enclosing_is_update)

    visit(tree, False)
    return count


def _collect_violations() -> dict[str, int]:
    """Return ``{repo_relative_path: broad_except_count}`` for behaviors/ files."""
    violations: dict[str, int] = {}
    for py_file, tree in _corpus.files_mentioning(
        "except", under=_BEHAVIORS_ROOT
    ):
        count = _count_broad_excepts_outside_update(tree)
        if count:
            rel = py_file.relative_to(_corpus.REPO_ROOT).as_posix()
            violations[rel] = count
    return violations


# ---------------------------------------------------------------------------
# Declared genuine boundaries — path -> (broad_except_count, reason).
#
# Each entry is a framework/execution/persistence boundary where the narrowest
# core-nameable covering type is ``Exception`` and the site carries an inline
# comment stating what it guards and why (CS-23-001 option 3).  The assertion is
# an exact match, so this list can ONLY SHRINK: adding a broad catch anywhere —
# including one more in a file already listed here — fails the test.
# ---------------------------------------------------------------------------
_DECLARED_EXCLUSIONS: dict[str, tuple[int, str]] = {
    "vultron/core/behaviors/bridge.py": (
        3,
        "BTBridge execution boundary (CONCERN-3019): a half-ticked tree must"
        " not escape into a FastAPI background task, so any node error is"
        " classified as internal_error and bt.shutdown() in finally must not"
        " replace the classified result.",
    ),
    "vultron/core/behaviors/inbox/_process_payload.py": (
        1,
        "inbox orchestrator tick loop: ticking a raw py_trees BehaviourTree is"
        " the execution boundary; any node error is logged and becomes"
        " Status.FAILURE rather than escaping process_payload().",
    ),
    "vultron/core/behaviors/case/nodes/proposal.py": (
        2,
        "boot-recovery persistence: an outbox read/enqueue failure while"
        " re-queuing a Create(VulnerabilityCase) obligation must fail the node,"
        " not crash server startup.",
    ),
    "vultron/core/behaviors/sync/nodes/ownership_offer_effect.py": (
        1,
        "SYNC-12-001: a write that could not persist a well-formed"
        " ownership-offer record IS a failed effect — return FAILURE so the"
        " Selector blocks PersistReceivedLogEntry.  Malformed snapshots are"
        " handled separately by a narrow ValidationError catch.",
    ),
}


def test_no_broad_except_outside_bt_update() -> None:
    """No broad ``except`` in behaviors/ outside a node's update() or the allow-list.

    CS-23-001.  The set of files with broad catches outside ``update()`` — and
    the count within each — must exactly equal ``_DECLARED_EXCLUSIONS``.
    """
    actual = _collect_violations()
    declared = {
        path: count for path, (count, _) in _DECLARED_EXCLUSIONS.items()
    }

    new_or_grown = {p: c for p, c in actual.items() if c != declared.get(p, 0)}
    resolved_or_shrunk = {
        p: declared[p] for p in declared if actual.get(p, 0) != declared[p]
    }

    lines: list[str] = []
    if new_or_grown:
        lines.append(
            "Broad `except Exception`/bare `except` outside a BT node's"
            " update() (CS-23-001). Narrow to the concrete type(s), delete and"
            " let it propagate, or — only at a genuine boundary — add an inline"
            " justification and a _DECLARED_EXCLUSIONS entry:"
        )
        for p in sorted(new_or_grown):
            lines.append(
                f"  {p}: found {actual[p]}, declared {declared.get(p, 0)}"
            )
    if resolved_or_shrunk:
        lines.append(
            "These declared exclusions no longer match (the list can only"
            " shrink — update _DECLARED_EXCLUSIONS to the new count or remove"
            " the entry):"
        )
        for p in sorted(resolved_or_shrunk):
            lines.append(
                f"  {p}: found {actual.get(p, 0)}, declared {declared[p]}"
            )

    assert actual == declared, "\n\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Synthetic detector-validation tests (parse via _corpus.parse_inline so the
# ratchet-hygiene meta-test stays satisfied, TB-13-003).
# ---------------------------------------------------------------------------


def test_detector_flags_broad_except_outside_update() -> None:
    tree = _corpus.parse_inline(
        "class N:\n"
        "    def _helper(self):\n"
        "        try:\n"
        "            do()\n"
        "        except Exception:\n"
        "            pass\n"
    )
    assert _count_broad_excepts_outside_update(tree) == 1


def test_detector_ignores_broad_except_inside_update() -> None:
    tree = _corpus.parse_inline(
        "class N:\n"
        "    def update(self):\n"
        "        try:\n"
        "            do()\n"
        "        except Exception:\n"
        "            return FAILURE\n"
    )
    assert _count_broad_excepts_outside_update(tree) == 0


def test_detector_flags_bare_except() -> None:
    tree = _corpus.parse_inline(
        "def f():\n"
        "    try:\n"
        "        do()\n"
        "    except:\n"
        "        pass\n"
    )
    assert _count_broad_excepts_outside_update(tree) == 1


def test_detector_flags_exception_in_tuple() -> None:
    tree = _corpus.parse_inline(
        "def f():\n"
        "    try:\n"
        "        do()\n"
        "    except (KeyError, Exception):\n"
        "        pass\n"
    )
    assert _count_broad_excepts_outside_update(tree) == 1


def test_detector_ignores_narrow_except() -> None:
    tree = _corpus.parse_inline(
        "def f():\n"
        "    try:\n"
        "        do()\n"
        "    except (KeyError, ValueError):\n"
        "        pass\n"
    )
    assert _count_broad_excepts_outside_update(tree) == 0


def test_detector_flags_broad_except_in_helper_nested_in_update() -> None:
    """A broad catch in a helper defined inside update() is NOT exempt.

    The exemption is for the update() body's own boundary catch, not for an
    arbitrary nested function's.
    """
    tree = _corpus.parse_inline(
        "class N:\n"
        "    def update(self):\n"
        "        def _inner():\n"
        "            try:\n"
        "                do()\n"
        "            except Exception:\n"
        "                pass\n"
        "        _inner()\n"
    )
    assert _count_broad_excepts_outside_update(tree) == 1


def test_declared_exclusions_have_reasons() -> None:
    """Every allow-list entry carries a non-empty reason (CS-23-001)."""
    for path, (count, reason) in _DECLARED_EXCLUSIONS.items():
        assert count >= 1, f"{path}: declared count must be >= 1"
        assert reason.strip(), f"{path}: allow-list entry needs a reason"
