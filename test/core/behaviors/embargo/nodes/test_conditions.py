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

"""Unit tests for embargo condition nodes (conditions.py)."""

import py_trees

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes.conditions import (
    IsActiveEmbargoNode,
    ValidateCaseExistsNode,
)
from vultron.core.states.em import EM

from test.core.behaviors.embargo.nodes.conftest import (
    make_case_and_embargo,
    setup_blackboard,
)


class TestValidateCaseExistsNode:
    """Tests for ValidateCaseExistsNode."""

    def test_returns_success_when_case_found(self):
        """Node returns SUCCESS when case exists in the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("vcn1")
        dl.create(case)

        setup_blackboard(dl)
        node = ValidateCaseExistsNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_failure_when_case_missing(self):
        """Node returns FAILURE when the case ID is not in the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        setup_blackboard(dl)

        node = ValidateCaseExistsNode(
            case_id="https://example.org/cases/nonexistent"
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE


class TestIsActiveEmbargoNode:
    """Tests for IsActiveEmbargoNode."""

    def test_returns_success_when_embargo_is_active(self):
        """Node returns SUCCESS when case.active_embargo matches embargo_id."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, embargo = make_case_and_embargo("ian1", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        node = IsActiveEmbargoNode(case_id=case.id_, embargo_id=embargo.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_failure_when_embargo_not_active(self):
        """Node returns FAILURE when active_embargo does not match."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, embargo = make_case_and_embargo("ian2", em_state=EM.PROPOSED)
        case.active_embargo = None
        dl.create(case)

        setup_blackboard(dl)
        node = IsActiveEmbargoNode(
            case_id=case.id_,
            embargo_id=embargo.id_,
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE

    def test_returns_failure_when_case_missing(self):
        """Node returns FAILURE when the case ID is not in the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        setup_blackboard(dl)

        node = IsActiveEmbargoNode(
            case_id="https://example.org/cases/nonexistent",
            embargo_id=(
                "https://example.org/cases/nonexistent/embargo_events/e1"
            ),
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE
