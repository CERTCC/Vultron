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
"""Tests for the close-report behavior tree (Phase 1 stub).

Verifies BT-18-004: factory param is accepted and used; default is the
correct fuzzer class.
"""

import py_trees

from vultron.core.behaviors.report.close_report_tree import (
    create_close_report_tree,
)
from vultron.demo.fuzzer.report_management.close_report import (
    OtherCloseCriteriaMet,
)

CASE_ID = "https://example.org/cases/test-001"


def test_create_close_report_tree_returns_behaviour():
    tree = create_close_report_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_default_is_other_close_criteria_met():
    tree = create_close_report_tree(case_id=CASE_ID)
    assert isinstance(tree, OtherCloseCriteriaMet)


def test_default_node_name():
    tree = create_close_report_tree(case_id=CASE_ID)
    assert tree.name == "OtherCloseCriteriaMet"


def test_custom_factory_used():
    sentinel = {"called": False}

    def custom_factory(name):
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomOtherClose")

    tree = create_close_report_tree(
        case_id=CASE_ID,
        other_close_criteria_factory=custom_factory,
    )
    assert sentinel["called"]
    assert tree.name == "CustomOtherClose"
    assert not isinstance(tree, OtherCloseCriteriaMet)


def test_pre_close_action_factory_accepted():
    """pre_close_action_factory is accepted (Phase 2 reserved, BT-18-004)."""
    tree = create_close_report_tree(case_id=CASE_ID)
    assert tree is not None


def test_pre_close_action_default_factory_produces_correct_node():
    """Default pre_close_action_factory produces a PreCloseAction node."""
    from vultron.core.behaviors.report.close_report_tree import (
        _default_pre_close_action_factory,
    )
    from vultron.demo.fuzzer.report_management.close_report import (
        PreCloseAction,
    )

    node = _default_pre_close_action_factory("PreCloseAction")
    assert isinstance(node, PreCloseAction)


def test_pre_close_action_custom_factory_accepted():
    """A custom pre_close_action_factory is accepted without error."""

    def custom_factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomPreClose")

    tree = create_close_report_tree(
        case_id=CASE_ID,
        pre_close_action_factory=custom_factory,
    )
    assert tree is not None
