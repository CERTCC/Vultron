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

"""Unit tests for CommitCaseLogEntryNode."""

from unittest.mock import patch

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.case.nodes import CommitCaseLogEntryNode
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.vultron_types import VultronCaseActor

_FACTORY_PATH = (
    "vultron.core.behaviors.case.nodes.create_commit_log_entry_tree"
)
_INNER_BRIDGE_PATH = "vultron.core.behaviors.case.nodes.BTBridge"

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-001"
ACTIVITY_ID = "https://example.org/activities/act-001"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def datalayer():
    dl = SqliteDataLayer("sqlite:///:memory:")
    actor = VultronCaseActor(id_=ACTOR_ID, name="Vendor Co")
    dl.create(actor)
    return dl


@pytest.fixture
def bridge(datalayer):
    return BTBridge(datalayer=datalayer)


# ---------------------------------------------------------------------------
# Helper: minimal VultronEvent-like object for blackboard
# ---------------------------------------------------------------------------


class _FakeActivity:
    """Minimal stand-in for a VultronEvent on the blackboard."""

    def __init__(
        self,
        activity_id: str = ACTIVITY_ID,
        semantic_type: MessageSemantics = MessageSemantics.CREATE_CASE,
    ):
        self.activity_id = activity_id
        self.semantic_type = semantic_type


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------


def test_node_instantiates_with_case_id():
    node = CommitCaseLogEntryNode(case_id=CASE_ID)
    assert node is not None
    assert node.name == "CommitCaseLogEntryNode"


def test_node_instantiates_without_case_id():
    node = CommitCaseLogEntryNode()
    assert node is not None


# ---------------------------------------------------------------------------
# Execution tests
# ---------------------------------------------------------------------------


def test_no_case_id_returns_success_without_building_inner_tree(bridge):
    """Node returns SUCCESS silently when no case_id is available (no-op)."""
    node = CommitCaseLogEntryNode()
    with patch(_FACTORY_PATH) as mock_factory, patch(
        _INNER_BRIDGE_PATH
    ) as mock_bridge:
        result = bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=None
        )
    assert result.status == Status.SUCCESS
    mock_factory.assert_not_called()
    mock_bridge.assert_not_called()


def test_constructor_case_id_builds_inner_commit_tree(bridge):
    """Node composes CommitLogEntryBT when case_id is given at build."""
    node = CommitCaseLogEntryNode(case_id=CASE_ID)
    with patch(_FACTORY_PATH) as mock_factory, patch(
        _INNER_BRIDGE_PATH
    ) as mock_bridge_cls:
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(status=Status.SUCCESS)
        )
        bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID, activity=None)
    mock_factory.assert_called_once_with(
        case_id=CASE_ID,
        object_id=CASE_ID,
        event_type="case_event",
    )
    execute_kwargs = (
        mock_bridge_cls.return_value.execute_with_setup.call_args.kwargs
    )
    assert execute_kwargs["actor_id"] == ACTOR_ID


def test_blackboard_case_id_builds_inner_commit_tree(bridge, datalayer):
    """Node reads case_id from blackboard written by a prior node."""
    node = CommitCaseLogEntryNode()  # no constructor param

    # Manually write case_id to the blackboard via a helper sequence node
    class _WriteCaseId(py_trees.behaviour.Behaviour):
        def __init__(self):
            super().__init__(name="_WriteCaseId")

        def setup(self, **kwargs):
            self.blackboard = self.attach_blackboard_client(
                name="_WriteCaseId"
            )
            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.WRITE
            )

        def update(self) -> Status:
            self.blackboard.case_id = CASE_ID
            return Status.SUCCESS

    seq = py_trees.composites.Sequence(
        name="TestSeq", memory=False, children=[_WriteCaseId(), node]
    )

    with patch(_FACTORY_PATH) as mock_factory, patch(
        _INNER_BRIDGE_PATH
    ) as mock_bridge_cls:
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(status=Status.SUCCESS)
        )
        bridge.execute_with_setup(tree=seq, actor_id=ACTOR_ID, activity=None)

    mock_factory.assert_called_once_with(
        case_id=CASE_ID,
        object_id=CASE_ID,
        event_type="case_event",
    )


def test_activity_on_blackboard_uses_semantic_type_as_event_type(bridge):
    """event_type is derived from activity.semantic_type.value."""
    activity = _FakeActivity(
        activity_id=ACTIVITY_ID,
        semantic_type=MessageSemantics.CREATE_CASE,
    )
    node = CommitCaseLogEntryNode(case_id=CASE_ID)
    with patch(_FACTORY_PATH) as mock_factory, patch(
        _INNER_BRIDGE_PATH
    ) as mock_bridge_cls:
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(status=Status.SUCCESS)
        )
        bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=activity
        )
    mock_factory.assert_called_once_with(
        case_id=CASE_ID,
        object_id=ACTIVITY_ID,
        event_type=MessageSemantics.CREATE_CASE.value,
    )


def test_no_activity_falls_back_to_case_event(bridge):
    """When no activity on blackboard, event_type defaults to 'case_event'."""
    node = CommitCaseLogEntryNode(case_id=CASE_ID)
    with patch(_FACTORY_PATH) as mock_factory, patch(
        _INNER_BRIDGE_PATH
    ) as mock_bridge_cls:
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(status=Status.SUCCESS)
        )
        bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID, activity=None)
    mock_factory.assert_called_once_with(
        case_id=CASE_ID,
        object_id=CASE_ID,
        event_type="case_event",
    )


def test_inner_commit_bt_failure_propagates(bridge):
    node = CommitCaseLogEntryNode(case_id=CASE_ID)
    with patch(_FACTORY_PATH) as mock_factory, patch(
        _INNER_BRIDGE_PATH
    ) as mock_bridge_cls:
        mock_factory.return_value = object()
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(
                status=Status.FAILURE, feedback_message="commit failed"
            )
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
    assert result.status == Status.FAILURE
