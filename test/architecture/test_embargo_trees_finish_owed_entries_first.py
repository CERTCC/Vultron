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

"""Every received embargo tree finishes an open embargo act first (CLP-07-015).

A failed commit can leave an embargo act with only some of its entries, and
the CASE_MANAGER must commit the rest before any later embargo act reads a
consent row (ADR-0146).  So in every received tree, a node that decides,
trial-applies or commits an embargo change runs after
``FinishOwedEmbargoEntriesNode``.

The embargo nodes are derived from code: every class under
``vultron/core/behaviors/`` whose body calls one of the copy-model helpers
(:data:`_EMBARGO_HELPERS`), and its subclasses.  The trees are every
received-side tree, built from its factory (``_received_tree_builds``).  The
trigger side is held by ``test/core/use_cases/triggers/test_base.py``: every
case-scoped trigger leads with the case-wide decisions, whose first is the
finishing step, and an embargo trigger that opts out takes it alone.
"""

import ast
import functools

import py_trees
import pytest

from test.architecture import _corpus
from test.architecture._received_tree_builds import built_received_trees
from vultron.core.behaviors.embargo.nodes.finish_owed import (
    FinishOwedEmbargoEntriesNode,
)

_BEHAVIORS_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"

#: The copy-model helpers an embargo act decides, trials or commits through.
_EMBARGO_HELPERS = frozenset(
    {
        "commit_and_apply_embargo_entries",
        "commit_and_apply_decision",
        "decide_commit_and_apply",
        "decide_on_stage",
        "trial_apply",
    }
)


@functools.cache
def _embargo_node_class_names() -> frozenset[str]:
    """Names of the classes whose own body calls a copy-model helper."""
    names: set[str] = set()
    for _, tree in _corpus.files_mentioning(
        *_EMBARGO_HELPERS, under=_BEHAVIORS_ROOT
    ):
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            if any(
                isinstance(call, ast.Call)
                and _corpus.callee_name(call.func) in _EMBARGO_HELPERS
                for call in ast.walk(cls)
            ):
                names.add(cls.name)
    return frozenset(names)


def _is_embargo_node(node: py_trees.behaviour.Behaviour) -> bool:
    names = _embargo_node_class_names()
    return any(cls.__name__ in names for cls in type(node).__mro__)


def _sites_with_embargo_nodes() -> list[tuple[str, str]]:
    return sorted(
        site
        for site, tree in built_received_trees().items()
        if any(_is_embargo_node(n) for n in tree.iterate())
    )


def test_the_embargo_node_inventory_is_not_empty() -> None:
    """The derivation finds the copy-model nodes, so the ratchet bites."""
    names = _embargo_node_class_names()
    assert {
        "CommitAndApplyEmbargoActivationNode",
        "ReissueStubInvitesNode",
        "_EmbargoLifecycleNode",
    } <= names
    assert len(_sites_with_embargo_nodes()) >= 5


@pytest.mark.spec("CLP-07-015")
@pytest.mark.parametrize(
    "site", _sites_with_embargo_nodes(), ids="{0[0]}:{0[1]}".format
)
def test_the_finishing_step_runs_before_every_embargo_node(
    site: tuple[str, str],
) -> None:
    order = list(built_received_trees()[site].iterate())
    # ``iterate()`` yields children before parents, so the tick order of the
    # leaves is the order they appear in.
    leaves = [n for n in order if not n.children]
    finishing = [
        i
        for i, n in enumerate(leaves)
        if isinstance(n, FinishOwedEmbargoEntriesNode)
    ]
    embargo = [i for i, n in enumerate(leaves) if _is_embargo_node(n)]

    assert finishing, f"{site[0]}:{site[1]}: no FinishOwedEmbargoEntriesNode"
    assert finishing[0] < embargo[0], (
        f"{site[0]}:{site[1]}: '{leaves[embargo[0]].name}' runs before the"
        " finishing step (CLP-07-015)"
    )
