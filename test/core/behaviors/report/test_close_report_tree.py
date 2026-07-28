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

Verifies BT-18-004/BT-23-003: bundle parameter is accepted and used;
DETERMINISTIC default produces AlwaysFail for OtherCloseCriteriaMet;
STOCHASTIC bundle produces the correct fuzzer class.
"""

import py_trees

from vultron.core.behaviors.report.close_report_tree import (
    create_close_report_tree,
)
from vultron.demo.fuzzer.base import AlwaysFail
from vultron.demo.fuzzer.bundles.close_report import (
    CLOSE_REPORT_DETERMINISTIC,
    CLOSE_REPORT_STOCHASTIC,
    CloseReportCallOutBundle,
)
from vultron.demo.fuzzer.report_management.close_report import (
    OtherCloseCriteriaMet,
    PreCloseAction,
)

CASE_ID = "https://example.org/cases/test-001"


def test_create_close_report_tree_returns_behaviour():
    tree = create_close_report_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_default_is_always_fail():
    """DETERMINISTIC default: OtherCloseCriteriaMet (p=0.25) → AlwaysFail (BT-23-002)."""
    tree = create_close_report_tree(case_id=CASE_ID)
    assert isinstance(tree, AlwaysFail)


def test_default_node_name():
    tree = create_close_report_tree(case_id=CASE_ID)
    assert tree.name == "OtherCloseCriteriaMet"


def test_stochastic_bundle_produces_fuzzer_node():
    tree = create_close_report_tree(
        case_id=CASE_ID, call_out=CLOSE_REPORT_STOCHASTIC
    )
    assert isinstance(tree, OtherCloseCriteriaMet)


def test_custom_factory_used():
    sentinel = {"called": False}

    def custom_factory(name):
        sentinel["called"] = True

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomOtherClose")

    bundle = CloseReportCallOutBundle(
        other_close_criteria_factory=custom_factory,  # type: ignore[arg-type]
    )
    tree = create_close_report_tree(case_id=CASE_ID, call_out=bundle)
    assert sentinel["called"]
    assert tree.name == "CustomOtherClose"
    assert not isinstance(tree, OtherCloseCriteriaMet)


def test_pre_close_action_factory_accepted():
    """pre_close_action_factory is accepted (Phase 2 reserved, BT-18-004)."""
    tree = create_close_report_tree(case_id=CASE_ID)
    assert tree is not None


def test_pre_close_action_bundle_field_produces_correct_node():
    """STOCHASTIC bundle pre_close_action_factory produces a PreCloseAction node."""
    node = CLOSE_REPORT_STOCHASTIC.pre_close_action_factory("PreCloseAction")
    assert isinstance(node, PreCloseAction)


def test_pre_close_action_custom_factory_accepted():
    """A custom pre_close_action_factory in a bundle is accepted without error."""

    def custom_factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomPreClose")

    bundle = CloseReportCallOutBundle(
        pre_close_action_factory=custom_factory,  # type: ignore[arg-type]
    )
    tree = create_close_report_tree(case_id=CASE_ID, call_out=bundle)
    assert tree is not None


def test_deterministic_singleton_accepted():
    tree = create_close_report_tree(
        case_id=CASE_ID, call_out=CLOSE_REPORT_DETERMINISTIC
    )
    assert isinstance(tree, py_trees.behaviour.Behaviour)
