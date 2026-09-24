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

"""Architecture invariant (DEMOCI-01-011): scenario ``_phase_*`` functions must
not call a raising ``wait_for_*`` helper outside a demo accumulation context.

Every ``wait_for_*`` / ``find_*`` polling helper in
``vultron/demo/helpers/polling.py`` raises ``AssertionError`` on timeout — the
correct contract for the unit tests that assert the timeout, but fatal inside a
scenario: ``scenario_harness`` re-raises, so a bare call crashes the whole run
at the first failure and buries every co-occurring failure (violating the
accumulation model, DEMOCI-01-003/004).

A raising wait invoked from scenario ``_phase_*`` code MUST therefore sit inside
a ``demo_step`` / ``demo_check`` / ``demo_gate`` block, OR be invoked through a
shared helper that performs that wrap internally so every caller inherits it
(``wait_for_participants_on_replicas`` and ``drain_phase1_ledger`` are the two
such helpers).

The raising / wrapping classification is derived from ``polling.py`` itself, so
a new raising helper is covered automatically and a new self-wrapping helper is
recognised as safe without editing this test.

Source: CONCERN-3384 (#3406), generalising the #1772/#1802 ledger-coverage fix.
Spec: ``specs/demo-ci.yaml`` DEMOCI-01-011.
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_DEMO_DIR = _corpus.REPO_ROOT / "vultron" / "demo"
_HELPERS_DIR = _DEMO_DIR / "helpers"
_SCENARIO_DIR = _DEMO_DIR / "scenario"
_POLLING = _HELPERS_DIR / "polling.py"

#: The demo failure-accumulation context managers (DEMOCI-01-004).
_DEMO_CONTEXTS = frozenset({"demo_step", "demo_check", "demo_gate"})

#: Prefixes of the polling-helper family in ``polling.py`` that block on a
#: side effect and raise on timeout.
_WAIT_PREFIXES = ("wait_for_", "find_", "drain_")


def _callee_name(call: ast.Call) -> str:
    """Return the called name for ``foo(...)`` or ``obj.foo(...)``."""
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return getattr(func, "id", "")


#: Names whose call raises on timeout: the low-level poll primitives plus the
#: whole ``wait_for_*`` / ``find_*`` polling family (they bottom out in one of
#: the primitives).  A helper that routes a call to any of these *outside* a
#: demo context can still crash a bare caller, so it is not "wrapping".
_POLL_PRIMITIVES = frozenset({"_poll_until", "_poll_datalayer_for"})


def _is_raising_callee(name: str) -> bool:
    return name in _POLL_PRIMITIVES or name.startswith(("wait_for_", "find_"))


def _parent_map(node: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(node):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def _call_in_demo_context(
    call: ast.AST, parents: dict[ast.AST, ast.AST]
) -> bool:
    """True if *call* has an ancestor ``with demo_step/check/gate(...):``."""
    cur = parents.get(call)
    while cur is not None:
        if isinstance(cur, ast.With) and any(
            isinstance(it.context_expr, ast.Call)
            and _callee_name(it.context_expr) in _DEMO_CONTEXTS
            for it in cur.items
        ):
            return True
        cur = parents.get(cur)
    return False


def _has_unwrapped_raising_call(fn: ast.AST) -> bool:
    """True if *fn* calls a raising poll helper outside any demo context.

    A helper is only safe to call bare from a scenario when *every* raising call
    it makes is inside a demo context.  A partial wrap — one raising call in a
    ``demo_check`` and another left bare — must still be treated as raising, or
    the DEMOCI-01-011 invariant silently stops being enforced for its callers.
    """
    parents = _parent_map(fn)
    for call in ast.walk(fn):
        if (
            isinstance(call, ast.Call)
            and _is_raising_callee(_callee_name(call))
            and not _call_in_demo_context(call, parents)
        ):
            return True
    return False


def _wraps_in_demo_context(node: ast.AST) -> bool:
    """True if *node* contains a ``with demo_step/check/gate(...):`` statement."""
    for inner in ast.walk(node):
        if not isinstance(inner, ast.With):
            continue
        for item in inner.items:
            ce = item.context_expr
            if isinstance(ce, ast.Call) and _callee_name(ce) in _DEMO_CONTEXTS:
                return True
    return False


def _polling_tree() -> ast.Module:
    """Return the parsed AST of ``polling.py`` from the shared corpus."""
    for path, tree in _corpus.files_mentioning(
        "def wait_for_", under=_HELPERS_DIR
    ):
        if path == _POLLING:
            assert isinstance(tree, ast.Module)
            return tree
    raise AssertionError(f"{_POLLING} not found in the source corpus")


def _classify_polling_helpers() -> tuple[frozenset[str], frozenset[str]]:
    """Return ``(raising, wrapping)`` helper-name sets derived from polling.py.

    A ``wait_for_*`` / ``find_*`` / ``drain_*`` function is a *wrapping* helper
    when it contains a demo context AND makes no raising poll call outside one —
    it neutralises the raise for every caller.  Otherwise it is a *raising*
    helper.  Bare raising helpers are the ones a scenario must not call outside
    a demo context; bare calls to wrapping helpers are safe.  Both ``def`` and
    ``async def`` at any nesting level are considered, so an async or
    conditionally-defined helper cannot slip through unclassified.
    """
    raising: set[str] = set()
    wrapping: set[str] = set()
    for node in ast.walk(_polling_tree()):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith(_WAIT_PREFIXES):
            continue
        if _wraps_in_demo_context(node) and not _has_unwrapped_raising_call(
            node
        ):
            wrapping.add(node.name)
        else:
            raising.add(node.name)
    return frozenset(raising), frozenset(wrapping)


_RAISING_WAITS, _WRAPPING_WAITS = _classify_polling_helpers()

_SCENARIO_TREES = {
    path: tree
    for path, tree in _corpus.files_mentioning(
        *_WAIT_PREFIXES, under=_SCENARIO_DIR
    )
    if path.name != "__init__.py"
}


def _bare_wait_violations(
    tree: ast.AST, raising: frozenset[str]
) -> list[tuple[int, str, str]]:
    """Return ``(line, phase_fn, callee)`` for bare raising waits in ``_phase_*``.

    A call is a violation when its callee is a known raising helper, it is
    lexically inside a function whose name starts with ``_phase_``, and no
    ancestor of the call is a ``with demo_*`` block.
    """
    parents = _parent_map(tree)
    violations: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("_phase_")
        ):
            continue
        for call in ast.walk(node):
            if (
                isinstance(call, ast.Call)
                and _callee_name(call) in raising
                and not _call_in_demo_context(call, parents)
            ):
                violations.append((call.lineno, node.name, _callee_name(call)))
    return violations


def test_polling_module_has_raising_and_wrapping_helpers():
    """Sanity: the classifier finds real helpers of each kind.

    Guards against a silently-empty ``_RAISING_WAITS`` (which would make the
    per-scenario check vacuous) and confirms the two known self-wrapping
    helpers are recognised.
    """
    assert "wait_for_case_participants" in _RAISING_WAITS
    assert _WRAPPING_WAITS >= {
        "wait_for_participants_on_replicas",
        "drain_phase1_ledger",
    }, (
        "wait_for_participants_on_replicas and drain_phase1_ledger must wrap "
        f"their raising poll internally (DEMOCI-01-011); got {_WRAPPING_WAITS}"
    )


@pytest.mark.parametrize(
    "scenario", sorted(_SCENARIO_TREES), ids=lambda p: p.name
)
def test_phase_functions_wrap_raising_waits(scenario: Path):
    """No ``_phase_*`` may call a raising ``wait_for_*`` outside a demo context.

    Wrap the call in ``demo_step`` / ``demo_check`` / ``demo_gate``, or route it
    through a shared helper that wraps internally (e.g.
    ``wait_for_participants_on_replicas``).  A bare raising wait crashes the
    whole run at the first timeout (DEMOCI-01-011).
    """
    violations = _bare_wait_violations(
        _SCENARIO_TREES[scenario], _RAISING_WAITS
    )
    assert not violations, (
        f"{scenario.relative_to(_corpus.REPO_ROOT)} calls raising wait helpers"
        f" outside a demo context in _phase_* code: {violations}. Wrap each in"
        " demo_step/demo_check/demo_gate, or route it through a shared helper"
        " that wraps internally (DEMOCI-01-011)."
    )


def test_the_check_can_actually_fail():
    """Guard: the detector must flag a genuine bare raising wait."""
    sample = _corpus.parse_inline(
        "def _phase_demo(client, case):\n"
        "    wait_for_case_participants(\n"
        "        vendor_client=client,\n"
        "        case_id=case.id_,\n"
        "        expected_actor_ids={a.id_, b.id_},\n"
        "    )\n"
    )
    violations = _bare_wait_violations(
        sample, frozenset({"wait_for_case_participants"})
    )
    assert len(violations) == 1
    assert violations[0][1] == "_phase_demo"
    assert violations[0][2] == "wait_for_case_participants"


def test_the_check_passes_when_wrapped():
    """Guard: a wait inside a demo_check block is not a violation."""
    sample = _corpus.parse_inline(
        "def _phase_demo(client, case):\n"
        "    with demo_check('participants present'):\n"
        "        wait_for_case_participants(\n"
        "            vendor_client=client,\n"
        "            case_id=case.id_,\n"
        "            expected_actor_ids={a.id_, b.id_},\n"
        "        )\n"
    )
    assert not _bare_wait_violations(
        sample, frozenset({"wait_for_case_participants"})
    )


def test_partial_wrap_is_classified_raising_not_wrapping():
    """A helper that leaves one raising call bare is not a safe wrapping helper.

    Guards ``_has_unwrapped_raising_call``: a body that wraps one poll in a
    demo_check but calls another bare must be treated as raising, so bare
    scenario callers are still flagged (DEMOCI-01-011).
    """
    partial = _corpus.parse_inline(
        "def wait_for_two_things(client, case):\n"
        "    with demo_check('first'):\n"
        "        wait_for_case_on_container(client, case.id_)\n"
        "    wait_for_case_participants(client, case.id_, set())\n"
    )
    assert isinstance(partial, ast.Module)
    fn = partial.body[0]
    assert _wraps_in_demo_context(fn)
    assert _has_unwrapped_raising_call(fn)

    fully = _corpus.parse_inline(
        "def wait_for_two_things(client, case):\n"
        "    with demo_check('first'):\n"
        "        wait_for_case_on_container(client, case.id_)\n"
        "    with demo_check('second'):\n"
        "        wait_for_case_participants(client, case.id_, set())\n"
    )
    assert isinstance(fully, ast.Module)
    assert not _has_unwrapped_raising_call(fully.body[0])
