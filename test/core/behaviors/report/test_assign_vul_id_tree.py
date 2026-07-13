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
"""Tests for the assign-VUL-ID behavior tree (Phase 1 stub).

Verifies BT-18-004: factory params are accepted and used; defaults are the
correct fuzzer classes.
"""

import py_trees

from vultron.core.behaviors.report.assign_vul_id_tree import (
    create_assign_vul_id_tree,
)
from vultron.demo.fuzzer.report_management.assign_vul_id import (
    IdAssignable,
    InScope,
)

CASE_ID = "https://example.org/cases/test-001"


def _marker_factory(label):
    def factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=label)

    return factory


def test_create_assign_vul_id_tree_returns_behaviour():
    tree = create_assign_vul_id_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_create_assign_vul_id_tree_root_name():
    tree = create_assign_vul_id_tree(case_id=CASE_ID)
    assert tree.name == "AssignVulIDBT"


def test_default_children_are_fuzzer_nodes():
    tree = create_assign_vul_id_tree(case_id=CASE_ID)
    assert len(tree.children) == 2
    assert isinstance(tree.children[0], InScope)
    assert isinstance(tree.children[1], IdAssignable)


def test_id_assignable_factory_used():
    sentinel = {"called": False}

    def custom_factory(name):
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomIdAssignable")

    tree = create_assign_vul_id_tree(
        case_id=CASE_ID,
        id_assignable_factory=custom_factory,
    )
    assert sentinel["called"]
    assert "CustomIdAssignable" in py_trees.display.ascii_tree(tree)


def test_in_scope_factory_used():
    sentinel = {"called": False}

    def custom_factory(name):
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomInScope")

    tree = create_assign_vul_id_tree(
        case_id=CASE_ID,
        in_scope_factory=custom_factory,
    )
    assert sentinel["called"]
    assert "CustomInScope" in py_trees.display.ascii_tree(tree)


def test_both_factories_replaceable():
    tree = create_assign_vul_id_tree(
        case_id=CASE_ID,
        id_assignable_factory=_marker_factory("IA"),
        in_scope_factory=_marker_factory("IS"),
    )
    tree_str = py_trees.display.ascii_tree(tree)
    assert "IA" in tree_str
    assert "IS" in tree_str
