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

"""The P/X/A embargo teardown is built in one received tree only (RSH-03-004).

``ThreatTerminationBranchNode`` is composed by ``add_participant_status_tree``
alone, under its CASE_MANAGER gate (``test_add_participant_status_bt.py``,
``test_teardown_branch_runs_only_at_the_case_manager``).  A replica therefore
never runs the teardown, so it never asks the CASE_MANAGER to end an embargo
the CASE_MANAGER declared public: it learns the teardown from the committed
ledger entries alone.  A second production call site would reopen that
question, so it fails here.

A call counts whether written bare, through a module attribute
(``nodes.ThreatTerminationBranchNode(...)``) or through an import alias.  The
teardown subtree itself, ``pxa_embargo_teardown_bt``, is out of scope: it is
built only inside ``ThreatTerminationBranchNode``, so the node's call sites
bound it.
"""

import ast

import pytest

from test.architecture import _corpus

_ALLOWED = {"vultron/core/behaviors/status/add_participant_status_tree.py"}


_NODE = "ThreatTerminationBranchNode"


def _aliases(tree: ast.AST) -> set[str]:
    """Every local name bound to the node class by an import alias."""
    return {
        alias.asname
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name == _NODE and alias.asname
    }


def _calls_node(call: ast.Call, names: set[str]) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id in names
    return isinstance(func, ast.Attribute) and func.attr == _NODE


def _call_sites() -> set[str]:
    sites: set[str] = set()
    for path in _corpus.paths_under(_corpus.REPO_ROOT / "vultron"):
        tree = _corpus.tree_of(path)
        names = {_NODE} | _aliases(tree)
        if any(
            isinstance(node, ast.Call) and _calls_node(node, names)
            for node in ast.walk(tree)
        ):
            sites.add(path.relative_to(_corpus.REPO_ROOT).as_posix())
    return sites


@pytest.mark.spec("RSH-03-004")
def test_only_the_participant_status_tree_builds_the_teardown_branch():
    assert _call_sites() == _ALLOWED


@pytest.mark.parametrize(
    "source",
    [
        "ThreatTerminationBranchNode(case_id=None)",
        "nodes.ThreatTerminationBranchNode(case_id=None)",
        "from x import ThreatTerminationBranchNode as T\nT(case_id=None)",
    ],
)
def test_every_call_form_is_counted(source: str):
    tree = _corpus.parse_inline(source)
    names = {_NODE} | _aliases(tree)
    assert any(
        isinstance(node, ast.Call) and _calls_node(node, names)
        for node in ast.walk(tree)
    )
