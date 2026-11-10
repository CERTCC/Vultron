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
"""Architecture ratchet: a test runs a use case or a tree as one act.

In production every tree run belongs to an act, which carries the act's
instant (ADR-0176).  A test that calls ``.execute()`` on a use case or
``BTBridge.execute_with_setup`` directly skips the act, so a node that reads
the instant finds none.  Tests go through ``test/support/act_runner.py``
(``run_in_act``, ``run_tree``, ``run_dispatch``) instead, and this test fails on a direct call
anywhere else under ``test/``.

A direct call is a call of ``.execute()`` with no arguments, of
``.execute_with_setup(...)``, or of ``.dispatch(event, dl, ...)``, on
anything but ``super()``.  A call inside a
method of that name is a test double's own body and is not counted.

:data:`DIRECT_RUN_EXEMPTIONS` is a pinned exemption set (ARCH-18-001): the
files that test the bridge's own act handling, or a run with no act, which
must call it bare.

Spec: CS-13-002 (time enters at the act's edge), ARCH-18-001.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from test.architecture import _corpus

_TEST_ROOT = _corpus.REPO_ROOT / "test"
_RUNNER = "test/support/act_runner.py"
_DIRECT_NAMES = ("execute", "execute_with_setup", "dispatch")

# Pinned exemption set: files that test how the bridge carries an act's
# instant, what a run with no act does, or the dispatcher's routing on a
# mock, so they call it without the runner on purpose.
# permanent: ADR-0176 (the runner is built on the behavior these files test)
DIRECT_RUN_EXEMPTIONS: frozenset[str] = frozenset(
    {
        "test/core/behaviors/test_act_instant.py",
        "test/core/behaviors/test_bridge.py",
        "test/core/behaviors/test_tree_nodes_read_act_instant.py",
        # Unit tests of the dispatcher's routing, on a mock store.
        "test/test_behavior_dispatcher.py",
    }
)


def _is_direct_run(node: ast.Call) -> bool:
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in _DIRECT_NAMES:
        return False
    if (
        isinstance(func.value, ast.Call)
        and isinstance(func.value.func, ast.Name)
        and func.value.func.id == "super"
    ):
        return False
    if func.attr == "execute":
        return not node.args and not node.keywords
    if func.attr == "dispatch":
        # A received dispatch takes the event and the store.
        return len(node.args) + len(node.keywords) >= 2
    return True


def direct_runs_in(tree: ast.AST) -> Iterator[int]:
    """Line numbers of the direct runs in *tree*; see the module docstring."""

    def visit(node: ast.AST, in_double: bool) -> Iterator[int]:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            in_double = in_double or node.name in _DIRECT_NAMES
        if (
            not in_double
            and isinstance(node, ast.Call)
            and _is_direct_run(node)
        ):
            yield node.lineno
        for child in ast.iter_child_nodes(node):
            yield from visit(child, in_double)

    yield from visit(tree, False)


def _direct_runs() -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for path, tree in _corpus.files_mentioning(
        *(f".{name}(" for name in _DIRECT_NAMES), under=_TEST_ROOT
    ):
        rel = Path(path).relative_to(_corpus.REPO_ROOT).as_posix()
        if rel == _RUNNER:
            continue
        lines = list(direct_runs_in(tree))
        if lines:
            found[rel] = lines
    return found


@pytest.mark.spec("CS-13-002")
@pytest.mark.spec("ARCH-18-001")
def test_tests_run_use_cases_and_trees_through_the_act_runner() -> None:
    found = _direct_runs()

    new = {p: ls for p, ls in found.items() if p not in DIRECT_RUN_EXEMPTIONS}
    stale = DIRECT_RUN_EXEMPTIONS - found.keys()
    assert not new, (
        "A test runs a use case or a tree outside an act (ADR-0176).  Use"
        " run_in_act(use_case), run_tree(bridge, tree, ...) or"
        " run_dispatch(dispatcher, event, dl) from"
        " test/support/act_runner.py:\n"
        + "\n".join(
            f"  {p}:{line}" for p, ls in sorted(new.items()) for line in ls
        )
    )
    assert not stale, (
        "Exempt files with no direct run left; delete them from"
        f" DIRECT_RUN_EXEMPTIONS (ARCH-18-002): {sorted(stale)}"
    )


_EVERY_SHAPE = """
def test_x(uc, bridge, tree):
    uc.execute()
    Thing(a, b).execute()
    bridge.execute_with_setup(tree, actor_id="a")
    dispatcher.dispatch(event, dl)
    super().execute()
    cursor.execute("select 1")
    queue.dispatch(event)


class Double:
    def execute(self):
        return self.inner.execute()
"""


@pytest.mark.spec("ARCH-18-001")
def test_the_finder_names_each_direct_run_and_nothing_else() -> None:
    lines = list(direct_runs_in(_corpus.parse_inline(_EVERY_SHAPE)))

    assert sorted(lines) == [3, 4, 5, 6]
