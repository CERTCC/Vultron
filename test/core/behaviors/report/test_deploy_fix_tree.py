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

Verifies BT-18-004: factory params are accepted and used; defaults are the
correct fuzzer classes.
"""

import pytest
import py_trees

from vultron.core.behaviors.report.deploy_fix_tree import (
    create_deploy_fix_tree,
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


def test_default_children_are_fuzzer_nodes():
    tree = create_deploy_fix_tree(case_id=CASE_ID)
    assert len(tree.children) == 5
    assert isinstance(tree.children[0], PrioritizeDeployment)
    assert isinstance(tree.children[1], DeployMitigation)
    assert isinstance(tree.children[2], MonitoringRequirement)
    assert isinstance(tree.children[3], DeployFix)
    assert isinstance(tree.children[4], MonitorDeployment)


@pytest.mark.parametrize(
    "param,label,index",
    [
        ("prioritize_deployment_factory", "PD", 0),
        ("deploy_mitigation_factory", "DM", 1),
        ("monitoring_requirement_factory", "MR", 2),
        ("deploy_fix_factory", "DF", 3),
        ("monitor_deployment_factory", "MD", 4),
    ],
)
def test_each_factory_is_wired(param, label, index):
    """Each factory parameter is individually wired into the tree."""
    sentinel = {"called": False}

    def custom_factory(name):
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=label)

    tree = create_deploy_fix_tree(case_id=CASE_ID, **{param: custom_factory})
    assert sentinel["called"]
    assert tree.children[index].name == label


def test_all_factories_replaceable():
    tree = create_deploy_fix_tree(
        case_id=CASE_ID,
        prioritize_deployment_factory=_marker_factory("PD"),
        deploy_mitigation_factory=_marker_factory("DM"),
        monitoring_requirement_factory=_marker_factory("MR"),
        deploy_fix_factory=_marker_factory("DF"),
        monitor_deployment_factory=_marker_factory("MD"),
    )
    tree_str = py_trees.display.ascii_tree(tree)
    for label in ("PD", "DM", "MR", "DF", "MD"):
        assert label in tree_str
