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
"""Tests for the publication behavior tree (Phase 1 stub).

Verifies BT-18-004: tree builder accepts a factory parameter and uses it to
construct the PrepareReport Composer call-out point.
"""

import py_trees

from vultron.core.behaviors.report.publication_tree import (
    create_publication_tree,
)
from vultron.demo.fuzzer.report_management.publication import PrepareReport

CASE_ID = "https://example.org/cases/test-001"


def test_create_publication_tree_returns_behaviour():
    """create_publication_tree returns a py_trees Behaviour."""
    tree = create_publication_tree(case_id=CASE_ID)
    assert isinstance(tree, py_trees.behaviour.Behaviour)


def test_create_publication_tree_default_is_prepare_report():
    """Default factory produces a PrepareReport node."""
    tree = create_publication_tree(case_id=CASE_ID)
    assert isinstance(tree, PrepareReport)


def test_create_publication_tree_custom_factory_used():
    """Custom prepare_report_factory is used when passed (BT-18-004)."""

    def custom_factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomPrepareReport")

    tree = create_publication_tree(
        case_id=CASE_ID,
        prepare_report_factory=custom_factory,
    )

    assert tree.name == "CustomPrepareReport"
    assert not isinstance(tree, PrepareReport)


def test_create_publication_tree_node_name_is_prepare_report():
    """Default node name is 'PrepareReport'."""
    tree = create_publication_tree(case_id=CASE_ID)
    assert tree.name == "PrepareReport"


def test_publish_factory_accepted():
    """publish_factory is accepted (Phase 2 reserved, BT-18-004)."""
    tree = create_publication_tree(case_id=CASE_ID)
    assert tree is not None


def test_publish_default_factory_produces_correct_node():
    """Default publish_factory produces a Publish node."""
    from vultron.core.behaviors.report.publication_tree import (
        _default_publish_factory,
    )
    from vultron.demo.fuzzer.report_management.publication import Publish

    node = _default_publish_factory("Publish")
    assert isinstance(node, Publish)


def test_publish_custom_factory_accepted():
    """A custom publish_factory is accepted without error."""

    def custom_factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomPublish")

    tree = create_publication_tree(
        case_id=CASE_ID,
        publish_factory=custom_factory,
    )
    assert tree is not None
