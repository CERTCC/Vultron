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
"""Only the CASE_MANAGER walks an RM closure path; a replica applies entries.

A replica is the case as seeded plus the ledger entries since (CM-23-016).
The CASE_MANAGER commits each RM step a ``Leave`` causes as its own status
entry, and a replica applies those entries (CM-23-001).  A replica that walked
``rm_closure_path()`` from its own stored RM state would write a step no entry
backs whenever it held an older status for the leaver (#4091).

So the closure path and its writer are named only where the CASE_MANAGER
writes a closure, and no node of the ledger-replay tree comes from one of
those modules.
"""

import ast
import inspect
from pathlib import Path

import pytest

from test.architecture import _corpus
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)

_CLOSURE_NAMES = ("rm_closure_path", "RMClosureWriter")

# permanent: CM-23-016 (the closure path is the CASE_MANAGER's to walk)
CLOSURE_PATH_MODULES: frozenset[str] = frozenset(
    {
        # Defines the path.
        "vultron/core/states/rm.py",
        # Writes it, one ordinary transition per step (RMB-14-005).
        "vultron/core/behaviors/case/nodes/participant/rm_closure.py",
        # The CASE_MANAGER's Leave advances, which report each step for the
        # record node to commit (CM-23-001, CM-23-005).
        "vultron/core/behaviors/case/nodes/leave/advance.py",
    }
)


def _code_names(tree: ast.AST) -> set[str]:
    """Every name *tree*'s code uses: identifiers, attributes and imports.

    Docstrings and comments are prose, not uses, so they do not count.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.alias, ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def _modules_naming_the_closure_path() -> set[str]:
    return {
        str(path.relative_to(_corpus.REPO_ROOT))
        for path, tree in _corpus.files_mentioning(
            *_CLOSURE_NAMES, under=_corpus.REPO_ROOT / "vultron"
        )
        if _code_names(tree) & set(_CLOSURE_NAMES)
    }


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("CM-23-001")
def test_only_case_manager_closure_sites_name_the_closure_path() -> None:
    """``rm_closure_path`` and ``RMClosureWriter`` stay in the pinned set."""
    assert _modules_naming_the_closure_path() == CLOSURE_PATH_MODULES


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("CM-23-001")
def test_no_ledger_replay_node_walks_the_closure_path() -> None:
    """No node of the replay tree is defined where a closure path is walked."""
    vultron_root = _corpus.REPO_ROOT / "vultron"
    modules = {
        Path(module)
        for node in create_announce_log_entry_tree().iterate()
        if (module := inspect.getsourcefile(type(node))) is not None
        and Path(module).is_relative_to(vultron_root)
    }
    assert modules, "the replay tree should be built from vultron nodes"
    walking = sorted(
        str(path.relative_to(_corpus.REPO_ROOT))
        for path in modules
        if _code_names(_corpus.tree_of(path)) & set(_CLOSURE_NAMES)
    )
    assert walking == []
