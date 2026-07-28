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
"""Factory injection tests for create_prioritize_subtree (BT-18-004/BT-23-003).

Verifies that evaluate_priority_factory is injected into the engage path and
that custom factories replace the default node in the tree (AC-4 for #1671).
Also verifies the two Phase 2 reserved factory parameters (enough_info_factory,
gather_info_factory) are accepted via bundle without error.
"""

import py_trees

from vultron.core.behaviors.report.prioritize_tree import (
    create_prioritize_subtree,
)
from vultron.demo.fuzzer.bundles.prioritization import (
    PrioritizationCallOutBundle,
)

CASE_ID = "https://example.org/cases/test-001"
ACTOR_ID = "https://example.org/actors/vendor"


def _marker_factory(label):
    def factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name=label)

    return factory


def test_evaluate_priority_factory_replaces_default_node():
    """Custom evaluate_priority_factory replaces the default node in the engage path (AC-4)."""
    CUSTOM_LABEL = "CustomEvaluator-sentinel"
    bundle = PrioritizationCallOutBundle(
        evaluate_priority_factory=_marker_factory(CUSTOM_LABEL),  # type: ignore[arg-type]
    )
    tree = create_prioritize_subtree(
        case_id=CASE_ID,
        actor_id=ACTOR_ID,
        call_out=bundle,
    )
    # Engage path is tree.children[0]; its first child is the evaluate_priority node
    engage_path = tree.children[0]
    assert engage_path.children[0].name == CUSTOM_LABEL


def test_evaluate_priority_factory_default_is_always_succeed():
    """Default evaluate_priority_factory produces an AlwaysSucceed node named EvaluateCasePriority."""
    from vultron.demo.fuzzer.base import AlwaysSucceed

    tree = create_prioritize_subtree(
        case_id=CASE_ID,
        actor_id=ACTOR_ID,
    )
    engage_path = tree.children[0]
    node = engage_path.children[0]
    assert node.name == "EvaluateCasePriority"
    assert isinstance(node, AlwaysSucceed)


def test_enough_info_factory_accepted():
    """enough_info_factory is accepted via bundle (Phase 2 reserved)."""
    bundle = PrioritizationCallOutBundle(
        enough_info_factory=_marker_factory("EnoughInfo"),  # type: ignore[arg-type]
    )
    tree = create_prioritize_subtree(
        case_id=CASE_ID,
        actor_id=ACTOR_ID,
        call_out=bundle,
    )
    assert tree is not None


def test_gather_info_factory_accepted():
    """gather_info_factory is accepted via bundle (Phase 2 reserved)."""
    bundle = PrioritizationCallOutBundle(
        gather_info_factory=_marker_factory("GatherInfo"),  # type: ignore[arg-type]
    )
    tree = create_prioritize_subtree(
        case_id=CASE_ID,
        actor_id=ACTOR_ID,
        call_out=bundle,
    )
    assert tree is not None


def test_both_phase2_factories_accepted_together():
    """Both Phase 2 reserved factories are accepted together via bundle."""
    bundle = PrioritizationCallOutBundle(
        enough_info_factory=_marker_factory("EnoughInfo"),  # type: ignore[arg-type]
        gather_info_factory=_marker_factory("GatherInfo"),  # type: ignore[arg-type]
    )
    tree = create_prioritize_subtree(
        case_id=CASE_ID,
        actor_id=ACTOR_ID,
        call_out=bundle,
    )
    assert tree is not None
