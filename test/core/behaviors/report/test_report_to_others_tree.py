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
"""Tests for the report-to-others behavior tree (Phase 1 stub).

Verifies BT-18-004: factory params are accepted and used; defaults are the
correct fuzzer classes.
"""

import pytest
import py_trees

from vultron.core.behaviors.report.report_to_others_tree import (
    create_report_to_others_tree,
)
from vultron.demo.fuzzer.report_management.report_to_others import (
    AllPartiesKnown,
    PolicyCompatible,
    RecipientEffortExceeded,
    TotalEffortLimitMet,
)

CASE_ID = "https://example.org/cases/test-001"


def _marker_factory(label):
    def factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=label)

    return factory


def test_create_report_to_others_tree_returns_behaviour():
    tree = create_report_to_others_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_create_report_to_others_tree_root_name():
    tree = create_report_to_others_tree(case_id=CASE_ID)
    assert tree.name == "ReportToOthersBT"


def test_default_children_are_fuzzer_nodes():
    tree = create_report_to_others_tree(case_id=CASE_ID)
    assert len(tree.children) == 4
    assert isinstance(tree.children[0], AllPartiesKnown)
    assert isinstance(tree.children[1], RecipientEffortExceeded)
    assert isinstance(tree.children[2], PolicyCompatible)
    assert isinstance(tree.children[3], TotalEffortLimitMet)


@pytest.mark.parametrize(
    "param,label,index",
    [
        ("all_parties_known_factory", "APK", 0),
        ("recipient_effort_exceeded_factory", "REE", 1),
        ("policy_compatible_factory", "PC", 2),
        ("total_effort_limit_factory", "TEL", 3),
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

    tree = create_report_to_others_tree(
        case_id=CASE_ID, **{param: custom_factory}
    )
    assert sentinel["called"]
    assert tree.children[index].name == label


def test_all_factories_replaceable():
    tree = create_report_to_others_tree(
        case_id=CASE_ID,
        all_parties_known_factory=_marker_factory("APK"),
        recipient_effort_exceeded_factory=_marker_factory("REE"),
        policy_compatible_factory=_marker_factory("PC"),
        total_effort_limit_factory=_marker_factory("TEL"),
    )
    tree_str = py_trees.display.ascii_tree(tree)
    for label in ("APK", "REE", "PC", "TEL"):
        assert label in tree_str
