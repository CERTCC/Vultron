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
"""Tests for the deploy-fix behavior tree (Phase 1 stub).

Verifies BT-18-004/BT-23-003: bundle parameter is accepted and used;
DETERMINISTIC default uses AlwaysSucceed/AlwaysFail per ceiling/floor rule;
STOCHASTIC bundle produces the correct fuzzer classes.
"""

import pytest
import py_trees

from vultron.core.behaviors.report.deploy_fix_tree import (
    create_deploy_fix_tree,
)
from vultron.demo.fuzzer.base import AlwaysFail, AlwaysSucceed
from vultron.demo.fuzzer.bundles.deploy_fix import (
    DEPLOY_FIX_DETERMINISTIC,
    DEPLOY_FIX_STOCHASTIC,
    DeployFixCallOutBundle,
)
from vultron.demo.fuzzer.report_management.deploy_fix import (
    DeployFix,
    DeployMitigation,
    MonitorDeployment,
    MonitoringRequirement,
    PrioritizeDeployment,
)

CASE_ID = "https://example.org/cases/test-001"


def _marker_factory(label):
    def factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=label)

    return factory


def test_create_deploy_fix_tree_returns_behaviour():
    tree = create_deploy_fix_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_create_deploy_fix_tree_root_name():
    tree = create_deploy_fix_tree(case_id=CASE_ID)
    assert tree.name == "DeployFixBT"


def test_default_children_are_deterministic():
    """DETERMINISTIC: ceiling/floor of each node's stochastic p (BT-23-002)."""
    tree = create_deploy_fix_tree(case_id=CASE_ID)
    assert len(tree.children) == 5
    assert isinstance(
        tree.children[0], AlwaysSucceed
    )  # PrioritizeDeployment p=0.90
    assert isinstance(
        tree.children[1], AlwaysSucceed
    )  # DeployMitigation p=0.75
    assert isinstance(
        tree.children[2], AlwaysSucceed
    )  # MonitoringRequirement p=0.70
    assert isinstance(tree.children[3], AlwaysFail)  # DeployFix p=0.10
    assert isinstance(
        tree.children[4], AlwaysSucceed
    )  # MonitorDeployment p=1.0


def test_stochastic_bundle_children_are_fuzzer_nodes():
    """STOCHASTIC bundle produces the correct fuzzer-class nodes."""
    tree = create_deploy_fix_tree(
        case_id=CASE_ID, call_out=DEPLOY_FIX_STOCHASTIC
    )
    assert len(tree.children) == 5
    assert isinstance(tree.children[0], PrioritizeDeployment)
    assert isinstance(tree.children[1], DeployMitigation)
    assert isinstance(tree.children[2], MonitoringRequirement)
    assert isinstance(tree.children[3], DeployFix)
    assert isinstance(tree.children[4], MonitorDeployment)


_BUNDLE_FIELDS = [
    ("prioritize_deployment_factory", "PD", 0),
    ("deploy_mitigation_factory", "DM", 1),
    ("monitoring_requirement_factory", "MR", 2),
    ("deploy_fix_factory", "DF", 3),
    ("monitor_deployment_factory", "MD", 4),
]


@pytest.mark.parametrize("field,label,index", _BUNDLE_FIELDS)
def test_each_factory_is_wired(field, label, index):
    """Each factory field in a bundle is individually wired into the tree."""
    sentinel = {"called": False}

    def custom_factory(name):
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=label)

    bundle = DeployFixCallOutBundle(**{field: custom_factory})  # type: ignore[arg-type]
    tree = create_deploy_fix_tree(case_id=CASE_ID, call_out=bundle)
    assert sentinel["called"]
    assert tree.children[index].name == label


def test_all_factories_replaceable():
    bundle = DeployFixCallOutBundle(
        prioritize_deployment_factory=_marker_factory("PD"),  # type: ignore[arg-type]
        deploy_mitigation_factory=_marker_factory("DM"),  # type: ignore[arg-type]
        monitoring_requirement_factory=_marker_factory("MR"),  # type: ignore[arg-type]
        deploy_fix_factory=_marker_factory("DF"),  # type: ignore[arg-type]
        monitor_deployment_factory=_marker_factory("MD"),  # type: ignore[arg-type]
    )
    tree = create_deploy_fix_tree(case_id=CASE_ID, call_out=bundle)
    tree_str = py_trees.display.ascii_tree(tree)
    for label in ("PD", "DM", "MR", "DF", "MD"):
        assert label in tree_str


def test_deterministic_singleton_accepted():
    tree = create_deploy_fix_tree(
        case_id=CASE_ID, call_out=DEPLOY_FIX_DETERMINISTIC
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)
