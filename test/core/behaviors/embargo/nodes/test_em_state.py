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

"""Unit tests for ReadEmStateNode and WriteEmStateNode (em_state.py).

Verifies AC-1, AC-2 of issue #1474: the em_state read/write BT nodes
follow DataLayerCondition / DataLayerAction base class patterns and
correctly replace the inline em_state accesses that previously lived in
the EmbargoLifecycle service methods.
"""

from unittest.mock import MagicMock, PropertyMock

import py_trees

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes.em_state import (
    ReadEmStateNode,
    WriteEmStateNode,
)
from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.em import EM
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

from test.core.behaviors.embargo.nodes.conftest import (
    make_case_and_embargo,
    setup_blackboard,
)


class TestReadEmStateNodeInheritance:
    """ReadEmStateNode follows the DataLayerCondition base class pattern (AC-2)."""

    def test_is_data_layer_condition(self):
        """ReadEmStateNode inherits from DataLayerCondition."""
        node = ReadEmStateNode(
            case_id="https://example.org/cases/test",
            result_out={},
        )
        assert isinstance(node, DataLayerCondition)


class TestReadEmStateNode:
    """ReadEmStateNode reads em_state from a case and stores it in result_out."""

    def test_returns_success_and_populates_em_before(self):
        """SUCCESS when case found with valid em_state; stores EM in result_out."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("rsn1", em_state=EM.ACTIVE)
        dl.create(case)
        setup_blackboard(dl)

        result_out: dict = {}
        node = ReadEmStateNode(case_id=case.id_, result_out=result_out)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert result_out["em_before"] == EM.ACTIVE

    def test_reads_revise_state(self):
        """SUCCESS when em_state is REVISE; returns EM.REVISE in result_out."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("rsn2", em_state=EM.REVISE)
        dl.create(case)
        setup_blackboard(dl)

        result_out: dict = {}
        node = ReadEmStateNode(case_id=case.id_, result_out=result_out)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert result_out["em_before"] == EM.REVISE

    def test_reads_none_state(self):
        """SUCCESS when em_state is NONE; returns EM.NONE in result_out."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("rsn3", em_state=EM.NONE)
        case.active_embargo = None
        dl.create(case)
        setup_blackboard(dl)

        result_out: dict = {}
        node = ReadEmStateNode(case_id=case.id_, result_out=result_out)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS
        assert result_out["em_before"] == EM.NONE

    def test_returns_failure_when_case_missing(self):
        """FAILURE when case_id is not in the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        setup_blackboard(dl)

        result_out: dict = {}
        node = ReadEmStateNode(
            case_id="https://example.org/cases/nonexistent",
            result_out=result_out,
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE
        assert "error" in result_out

    def test_returns_failure_when_datalayer_not_set(self):
        """FAILURE when datalayer is None (direct invocation without BTBridge)."""
        result_out: dict = {}
        node = ReadEmStateNode(
            case_id="https://example.org/cases/any",
            result_out=result_out,
        )
        node.datalayer = None  # explicitly unset

        status = node.update()

        assert status == py_trees.common.Status.FAILURE

    def test_returns_failure_when_current_status_raises_value_error(self):
        """FAILURE when case.current_status raises ValueError (no materialized status)."""
        from vultron.core.models.case import VulnerabilityCase

        mock_case = MagicMock(spec=VulnerabilityCase)
        type(mock_case).current_status = PropertyMock(
            side_effect=ValueError("no materialized CaseStatus")
        )
        mock_dl = MagicMock()
        mock_dl.read.return_value = mock_case

        result_out: dict = {}
        node = ReadEmStateNode(
            case_id="https://example.org/cases/any",
            result_out=result_out,
        )
        node.datalayer = mock_dl

        status = node.update()

        assert status == py_trees.common.Status.FAILURE
        assert "error" in result_out


class TestWriteEmStateNodeInheritance:
    """WriteEmStateNode follows the DataLayerAction base class pattern (AC-2)."""

    def test_is_data_layer_action(self):
        """WriteEmStateNode inherits from DataLayerAction."""
        node = WriteEmStateNode(
            case_id="https://example.org/cases/test",
            result_out={},
        )
        assert isinstance(node, DataLayerAction)


class TestWriteEmStateNode:
    """WriteEmStateNode writes em_after from result_out to the case."""

    def test_writes_em_after_and_persists(self):
        """SUCCESS and em_state updated on case when result_out has em_after."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("wsn1", em_state=EM.PROPOSED)
        case.active_embargo = None
        dl.create(case)
        setup_blackboard(dl)

        result_out: dict = {"em_after": EM.ACTIVE}
        node = WriteEmStateNode(case_id=case.id_, result_out=result_out)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

        updated_case = dl.read(case.id_)
        assert isinstance(updated_case, VulnerabilityCase)
        assert updated_case.current_status.em.state == EM.ACTIVE

    def test_idempotent_when_already_at_target(self):
        """SUCCESS without saving when em_state already equals em_after."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("wsn2", em_state=EM.ACTIVE)
        dl.create(case)
        setup_blackboard(dl)

        result_out: dict = {"em_after": EM.ACTIVE}
        node = WriteEmStateNode(case_id=case.id_, result_out=result_out)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.SUCCESS

    def test_returns_failure_when_em_after_missing(self):
        """FAILURE when result_out['em_after'] is absent."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("wsn3", em_state=EM.ACTIVE)
        dl.create(case)
        setup_blackboard(dl)

        result_out: dict = {}  # no em_after key
        node = WriteEmStateNode(case_id=case.id_, result_out=result_out)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE

    def test_returns_failure_when_em_after_not_em_type(self):
        """FAILURE when result_out['em_after'] is not an EM enum value."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("wsn4", em_state=EM.ACTIVE)
        dl.create(case)
        setup_blackboard(dl)

        result_out: dict = {"em_after": "ACTIVE"}  # string, not EM enum
        node = WriteEmStateNode(case_id=case.id_, result_out=result_out)
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE

    def test_returns_failure_when_case_missing(self):
        """FAILURE when case_id not found in the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        setup_blackboard(dl)

        result_out: dict = {"em_after": EM.EXITED}
        node = WriteEmStateNode(
            case_id="https://example.org/cases/nonexistent",
            result_out=result_out,
        )
        bt = py_trees.trees.BehaviourTree(root=node)
        bt.setup()
        bt.tick()

        assert node.status == py_trees.common.Status.FAILURE

    def test_returns_failure_when_datalayer_not_set(self):
        """FAILURE when datalayer is None (direct invocation without BTBridge)."""
        result_out: dict = {"em_after": EM.EXITED}
        node = WriteEmStateNode(
            case_id="https://example.org/cases/any",
            result_out=result_out,
        )
        node.datalayer = None

        status = node.update()

        assert status == py_trees.common.Status.FAILURE


class TestReadWriteEmStateIntegration:
    """Round-trip: ReadEmStateNode → WriteEmStateNode applies the state change."""

    def test_read_then_write_transitions_em_state(self):
        """Read PROPOSED, write ACTIVE: case persists EM.ACTIVE."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = make_case_and_embargo("rw1", em_state=EM.PROPOSED)
        case.active_embargo = None
        dl.create(case)
        setup_blackboard(dl)

        result_out: dict = {}

        read_node = ReadEmStateNode(case_id=case.id_, result_out=result_out)
        read_node.datalayer = dl
        assert read_node.update() == py_trees.common.Status.SUCCESS
        assert result_out["em_before"] == EM.PROPOSED

        result_out["em_after"] = EM.ACTIVE
        write_node = WriteEmStateNode(case_id=case.id_, result_out=result_out)
        write_node.datalayer = dl
        assert write_node.update() == py_trees.common.Status.SUCCESS

        updated_case = dl.read(case.id_)
        assert isinstance(updated_case, VulnerabilityCase)
        assert updated_case.current_status.em.state == EM.ACTIVE
