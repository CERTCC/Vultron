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
    HasActiveEmbargoNode,
    HasCaseStatusesNode,
    IsActiveEmbargoNode,
    ValidateCaseExistsNode,
)
from vultron.core.states.em import EM
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

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


class TestHasActiveEmbargoNode:
    """Tests for HasActiveEmbargoNode."""

    def test_returns_success_when_active_embargo_present(self):
        """Node returns SUCCESS when case.active_embargo is non-None."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("hae1", em_state=EM.ACTIVE)
        dl.create(case)

        setup_blackboard(dl)
        result_out: dict = {}
        node = HasActiveEmbargoNode(case_id=case.id_, result_out=result_out)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert "error" not in result_out

    def test_returns_failure_when_no_active_embargo(self):
        """Node returns FAILURE when active_embargo is None."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("hae2")
        case.active_embargo = None
        dl.create(case)

        setup_blackboard(dl)
        result_out: dict = {}
        node = HasActiveEmbargoNode(case_id=case.id_, result_out=result_out)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE
        assert isinstance(
            result_out["error"], VultronInvalidStateTransitionError
        )

    def test_returns_failure_when_case_missing(self):
        """Node returns FAILURE when the case is not in the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        setup_blackboard(dl)

        result_out: dict = {}
        node = HasActiveEmbargoNode(
            case_id="https://example.org/cases/nonexistent",
            result_out=result_out,
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE

    def test_error_message_includes_case_id(self):
        """result_out['error'] message references the case ID."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("hae3")
        case.active_embargo = None
        dl.create(case)

        setup_blackboard(dl)
        result_out: dict = {}
        node = HasActiveEmbargoNode(case_id=case.id_, result_out=result_out)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert case.id_ in str(result_out["error"])


class TestHasCaseStatusesNode:
    """Tests for HasCaseStatusesNode."""

    def test_returns_success_when_case_statuses_non_empty(self):
        """Node returns SUCCESS when case has at least one CaseStatus entry."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/hcs1",
            case_statuses=[as_CaseStatus(em_state=EM.ACTIVE)],
        )
        dl.create(case)

        setup_blackboard(dl)
        node = HasCaseStatusesNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_failure_when_case_statuses_empty(self):
        """Node returns FAILURE when case.case_statuses is empty."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/hcs2",
            case_statuses=[],
        )
        dl.create(case)

        setup_blackboard(dl)
        node = HasCaseStatusesNode(case_id=case.id_)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE

    def test_returns_failure_when_case_missing(self):
        """Node returns FAILURE when the case is not in the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        setup_blackboard(dl)

        node = HasCaseStatusesNode(
            case_id="https://example.org/cases/nonexistent"
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE
