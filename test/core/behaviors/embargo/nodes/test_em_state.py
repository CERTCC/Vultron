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

"""Unit tests for ReadEmStateNode (em_state.py)."""

from unittest.mock import MagicMock, PropertyMock

import py_trees
import pytest

from test.core.behaviors.embargo.nodes.conftest import (
    make_case_and_embargo,
    setup_blackboard,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes.em_state import (
    ReadEmStateNode,
    read_case_em_state,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.states.em import EM
from vultron.errors import BtNodePreconditionError
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)


class TestReadEmStateNodeInheritance:
    """ReadEmStateNode follows the DataLayerCondition base class pattern (AC-2)."""

    def test_is_data_layer_condition(self):
        """ReadEmStateNode inherits from DataLayerConditionWithPorts."""
        node = ReadEmStateNode(
            case_id="https://example.org/cases/test",
            result_out={},
        )
        assert isinstance(node, DataLayerConditionWithPorts)


class TestReadEmStateNode:
    """ReadEmStateNode reads em_state from a case and stores it in result_out."""

    def test_returns_success_and_populates_em_before(self):
        """SUCCESS when case found with valid em_state; stores EM in result_out."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
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
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
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
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case, _ = make_case_and_embargo("rsn3", em_state=EM.NONE)
        case.set_embargo(None)
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
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
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
        mock_dl.read_case.return_value = mock_case

        result_out: dict = {}
        node = ReadEmStateNode(
            case_id="https://example.org/cases/any",
            result_out=result_out,
        )
        node.datalayer = mock_dl

        status = node.update()

        assert status == py_trees.common.Status.FAILURE
        assert "error" in result_out


class TestReadCaseEmState:
    """``read_case_em_state`` returns the EM state or raises (BT-HELPER-01)."""

    @staticmethod
    def _dl() -> SqliteDataLayer:
        return SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )

    def test_returns_em_state_and_fills_result_out(self):
        dl = self._dl()
        case, _ = make_case_and_embargo("rces1", em_state=EM.REVISE)
        dl.create(case)

        result_out: dict[str, object] = {}
        assert read_case_em_state(dl, case.id_, result_out) == EM.REVISE
        assert result_out["em_before"] == EM.REVISE

    def test_result_out_is_optional(self):
        dl = self._dl()
        case, _ = make_case_and_embargo("rces2", em_state=EM.EXITED)
        dl.create(case)

        assert read_case_em_state(dl, case.id_) == EM.EXITED

    def test_missing_case_raises_and_records_error(self):
        dl = self._dl()
        absent = "https://example.org/cases/absent"
        result_out: dict[str, object] = {}

        with pytest.raises(BtNodePreconditionError, match=absent):
            read_case_em_state(dl, absent, result_out)
        assert "error" in result_out

    def test_stale_em_before_does_not_mask_a_failed_read(self):
        """A shared dict still holding an earlier tick's state must not turn
        a failed read into a success."""
        dl = self._dl()
        result_out: dict[str, object] = {"em_before": EM.ACTIVE}

        with pytest.raises(BtNodePreconditionError):
            read_case_em_state(
                dl, "https://example.org/cases/absent", result_out
            )
