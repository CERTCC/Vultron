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
"""Tests for the deploy-tree combinator factory (issue #1985, BT-20-005).

Covers all acceptance criteria:

- AC-1: ``deploy_tree.py`` with ``create_deploy_tree(case_id, actor_id,
  fix_call_out, mitigation_call_out)`` building a ``DeployOrMitigateBT``
  Fallback with the fix arm first.
- AC-2: Fix arm delegates to ``create_deploy_fix_tree``; mitigation arm
  delegates to ``create_deploy_mitigation_tree``.
- AC-3: Unit tests covering tree structure and factory delegation.
"""

import py_trees

from vultron.core.behaviors.call_out.bundles.deploy_fix import (
    DEPLOY_FIX_DETERMINISTIC,
    DeployFixCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.deploy_mitigation import (
    DEPLOY_MITIGATION_DETERMINISTIC,
    DeployMitigationCallOutBundle,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.report.deploy_fix_tree import (
    create_deploy_fix_tree,
)
from vultron.core.behaviors.report.deploy_mitigation_tree import (
    create_deploy_mitigation_tree,
)
from vultron.core.behaviors.report.deploy_tree import create_deploy_tree

CASE_ID = "https://example.org/cases/test-deploy-combinator-001"
ACTOR_ID = "https://example.org/actors/deployer-combinator-001"


# ---------------------------------------------------------------------------
# AC-1: Tree structure — root is Fallback named "DeployOrMitigateBT" with 2 arms
# ---------------------------------------------------------------------------


def test_create_deploy_tree_returns_behaviour():
    tree = create_deploy_tree(case_id=CASE_ID, actor_id=ACTOR_ID)
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_create_deploy_tree_root_name():
    """Root Fallback is named 'DeployOrMitigateBT' (AC-1)."""
    tree = create_deploy_tree(case_id=CASE_ID, actor_id=ACTOR_ID)
    assert tree.name == "DeployOrMitigateBT"


def test_tree_root_is_fallback():
    """Root node is a py_trees Selector (Fallback) (AC-1)."""
    tree = create_deploy_tree(case_id=CASE_ID, actor_id=ACTOR_ID)
    assert isinstance(tree, py_trees.composites.Selector)


def test_tree_has_exactly_two_arms():
    """DeployOrMitigateBT has exactly two children: fix arm then mitigation arm (AC-1)."""
    tree = create_deploy_tree(case_id=CASE_ID, actor_id=ACTOR_ID)
    assert len(tree.children) == 2


def test_fix_arm_is_first():
    """Fix arm (DeployFixBT) is child[0] — preferred over mitigation (AC-1)."""
    tree = create_deploy_tree(case_id=CASE_ID, actor_id=ACTOR_ID)
    assert tree.children[0].name == "DeployFixBT"


def test_mitigation_arm_is_second():
    """Mitigation arm (DeployMitigationBT) is child[1] — fallback (AC-1)."""
    tree = create_deploy_tree(case_id=CASE_ID, actor_id=ACTOR_ID)
    assert tree.children[1].name == "DeployMitigationBT"


# ---------------------------------------------------------------------------
# AC-2: Fix arm delegates to create_deploy_fix_tree;
#        mitigation arm delegates to create_deploy_mitigation_tree
# ---------------------------------------------------------------------------


def test_fix_arm_matches_standalone_deploy_fix_tree():
    """Fix arm has the same structure as a standalone create_deploy_fix_tree (AC-2)."""
    tree = create_deploy_tree(case_id=CASE_ID, actor_id=ACTOR_ID)
    standalone = create_deploy_fix_tree(case_id=CASE_ID, actor_id=ACTOR_ID)
    assert tree.children[0].name == standalone.name
    assert len(tree.children[0].children) == len(standalone.children)


def test_mitigation_arm_matches_standalone_deploy_mitigation_tree():
    """Mitigation arm has the same structure as a standalone create_deploy_mitigation_tree (AC-2)."""
    tree = create_deploy_tree(case_id=CASE_ID, actor_id=ACTOR_ID)
    standalone = create_deploy_mitigation_tree(
        case_id=CASE_ID, actor_id=ACTOR_ID
    )
    assert tree.children[1].name == standalone.name
    assert len(tree.children[1].children) == len(standalone.children)


# ---------------------------------------------------------------------------
# AC-2 / AC-3: Bundle injection — fix_call_out and mitigation_call_out are forwarded
# ---------------------------------------------------------------------------


def test_fix_call_out_bundle_forwarded_to_fix_arm():
    """fix_call_out bundle is forwarded to the fix arm (AC-2)."""
    sentinel = {"called": False}

    def custom_deploy_fix(name: str) -> py_trees.behaviour.Behaviour:
        sentinel["called"] = True
        return AlwaysSucceed(name)

    bundle = DeployFixCallOutBundle(
        deploy_fix_factory=custom_deploy_fix,  # type: ignore[arg-type]
    )
    create_deploy_tree(case_id=CASE_ID, actor_id=ACTOR_ID, fix_call_out=bundle)
    assert sentinel["called"]


def test_mitigation_call_out_bundle_forwarded_to_mitigation_arm():
    """mitigation_call_out bundle is forwarded to the mitigation arm (AC-2)."""
    sentinel = {"called": False}

    def custom_mitigation_deployed(name: str) -> py_trees.behaviour.Behaviour:
        sentinel["called"] = True
        return AlwaysFail(name)

    bundle = DeployMitigationCallOutBundle(
        mitigation_deployed_factory=custom_mitigation_deployed,  # type: ignore[arg-type]
    )
    create_deploy_tree(
        case_id=CASE_ID, actor_id=ACTOR_ID, mitigation_call_out=bundle
    )
    assert sentinel["called"]


def test_default_bundles_are_deterministic_singletons():
    """Default call_out=None uses DETERMINISTIC singletons for both arms (AC-3).

    Checks only what the combinator owns: that the fix arm contains a
    "DeployFix" node backed by AlwaysFail (p=0.10 ceiling) and the mitigation
    arm's first child is named "MitigationDeployed" and is AlwaysFail
    (p=0.25 floor).  Uses name-based lookup so adding guards inside either
    subtree does not silently misdirect the assertion.
    """
    tree = create_deploy_tree(case_id=CASE_ID, actor_id=ACTOR_ID)
    fix_arm = tree.children[0]
    mit_arm = tree.children[1]

    # Fix arm: locate DeployFix call-out node by name, verify AlwaysFail
    deploy_if_ready = next(
        c for c in fix_arm.children if c.name == "_DeployFixIfReady"
    )
    deploy_fix_node = next(
        c for c in deploy_if_ready.children if c.name == "DeployFix"
    )
    assert isinstance(deploy_fix_node, AlwaysFail)

    # Mitigation arm: MitigationDeployed is arm's first child (direct Fallback child)
    assert mit_arm.children[0].name == "MitigationDeployed"
    assert isinstance(mit_arm.children[0], AlwaysFail)


def test_explicit_deterministic_bundles_accepted():
    """Passing DETERMINISTIC singletons explicitly produces the same tree (AC-3)."""
    tree = create_deploy_tree(
        case_id=CASE_ID,
        actor_id=ACTOR_ID,
        fix_call_out=DEPLOY_FIX_DETERMINISTIC,
        mitigation_call_out=DEPLOY_MITIGATION_DETERMINISTIC,
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)
    assert tree.name == "DeployOrMitigateBT"


# ---------------------------------------------------------------------------
# AC-3: Fallback ordering — fix arm is tried before mitigation arm
# ---------------------------------------------------------------------------


def test_both_bundles_are_invoked_during_construction():
    """Both fix and mitigation bundles are called when the tree is built (AC-2/3).

    Verifies that `fix_call_out` and `mitigation_call_out` are each forwarded
    to their respective subtree factories during construction — confirmed by
    sentinel dicts in custom factory functions.

    Note: tick-level Fallback ordering (fix succeeds → mitigation skipped) is
    deferred to a DataLayer integration test (see follow-up issue).
    """
    fix_invoked = {"called": False}
    mit_invoked = {"called": False}

    def tracking_deploy_fix(name: str) -> py_trees.behaviour.Behaviour:
        fix_invoked["called"] = True
        return AlwaysSucceed(name)

    def tracking_mitigation_deployed(
        name: str,
    ) -> py_trees.behaviour.Behaviour:
        mit_invoked["called"] = True
        return AlwaysFail(name)

    fix_bundle = DeployFixCallOutBundle(
        deploy_fix_factory=tracking_deploy_fix,  # type: ignore[arg-type]
    )
    mit_bundle = DeployMitigationCallOutBundle(
        mitigation_deployed_factory=tracking_mitigation_deployed,  # type: ignore[arg-type]
    )

    create_deploy_tree(
        case_id=CASE_ID,
        actor_id=ACTOR_ID,
        fix_call_out=fix_bundle,
        mitigation_call_out=mit_bundle,
    )

    assert fix_invoked["called"]
    assert mit_invoked["called"]


def test_tree_ascii_contains_both_arm_names():
    """ASCII tree representation includes both subtree root names (AC-3)."""
    tree = create_deploy_tree(case_id=CASE_ID, actor_id=ACTOR_ID)
    tree_str = py_trees.display.ascii_tree(tree)
    assert "DeployFixBT" in tree_str
    assert "DeployMitigationBT" in tree_str
