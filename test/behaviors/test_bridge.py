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

"""Unit tests for BT bridge layer."""

import pytest
import py_trees
from py_trees.common import Status

from vultron.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer

# Test behavior nodes for verifying bridge functionality


class AlwaysSucceed(py_trees.behaviour.Behaviour):
    """Test node that always succeeds immediately."""

    def __init__(self, name: str = "AlwaysSucceed"):
        super().__init__(name=name)

    def update(self) -> Status:
        self.logger.debug("AlwaysSucceed: returning SUCCESS")
        self.feedback_message = "Success"
        return Status.SUCCESS


class AlwaysFail(py_trees.behaviour.Behaviour):
    """Test node that always fails immediately."""

    def __init__(self, name: str = "AlwaysFail"):
        super().__init__(name=name)

    def update(self) -> Status:
        self.logger.debug("AlwaysFail: returning FAILURE")
        self.feedback_message = "Failure"
        return Status.FAILURE


class RunNTimes(py_trees.behaviour.Behaviour):
    """Test node that runs N times before succeeding."""

    def __init__(self, n: int, name: str = "RunNTimes"):
        super().__init__(name=name)
        self.target_ticks = n
        self.tick_count = 0

    def initialise(self) -> None:
        self.tick_count = 0

    def update(self) -> Status:
        self.tick_count += 1
        self.logger.debug(
            f"RunNTimes: tick {self.tick_count}/{self.target_ticks}"
        )

        if self.tick_count < self.target_ticks:
            self.feedback_message = (
                f"Running: {self.tick_count}/{self.target_ticks}"
            )
            return Status.RUNNING

        self.feedback_message = f"Completed after {self.tick_count} ticks"
        return Status.SUCCESS


class CheckBlackboard(py_trees.behaviour.Behaviour):
    """Test node that verifies blackboard data is accessible."""

    def __init__(self, name: str = "CheckBlackboard"):
        super().__init__(name=name)

    def setup(self, **kwargs) -> None:
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(
            key="datalayer", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="actor_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        try:
            # Verify required keys exist
            datalayer = self.blackboard.datalayer
            actor_id = self.blackboard.actor_id

            if datalayer is None or actor_id is None:
                self.feedback_message = "Missing required blackboard data"
                return Status.FAILURE

            self.feedback_message = f"Blackboard verified for actor {actor_id}"
            return Status.SUCCESS

        except KeyError as e:
            self.feedback_message = f"Missing blackboard key: {e}"
            return Status.FAILURE


class ExceptionNode(py_trees.behaviour.Behaviour):
    """Test node that raises an exception during execution."""

    def __init__(self, name: str = "ExceptionNode"):
        super().__init__(name=name)

    def update(self) -> Status:
        self.logger.debug("ExceptionNode: raising exception")
        raise RuntimeError("Intentional test exception")


# Fixtures


@pytest.fixture
def datalayer():
    """Provide in-memory TinyDB data layer."""
    return TinyDbDataLayer(db_path=None)


@pytest.fixture
def bridge(datalayer):
    """Provide BTBridge instance with data layer."""
    return BTBridge(datalayer=datalayer)


@pytest.fixture
def test_actor_id():
    """Provide test actor ID."""
    return "https://example.org/actors/test-actor"


# Tests for setup_tree


def test_setup_tree_basic(bridge, test_actor_id):
    """Test basic tree setup with actor ID."""
    tree = AlwaysSucceed()
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    assert isinstance(bt, py_trees.trees.BehaviourTree)
    assert bt.root == tree


def test_setup_tree_populates_blackboard(bridge, datalayer, test_actor_id):
    """Test blackboard populated with datalayer and actor_id."""
    tree = CheckBlackboard()
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    # Setup tree to initialize nodes
    bt.setup()

    # Verify blackboard accessible via global blackboard
    blackboard = py_trees.blackboard.Client(name="test")
    blackboard.register_key(
        key="datalayer", access=py_trees.common.Access.READ
    )
    blackboard.register_key(key="actor_id", access=py_trees.common.Access.READ)

    assert blackboard.datalayer == datalayer
    assert blackboard.actor_id == test_actor_id


def test_setup_tree_with_activity(bridge, test_actor_id):
    """Test blackboard populated with activity."""
    tree = AlwaysSucceed()
    test_activity = {"type": "Create", "object": {"type": "Note"}}

    bt = bridge.setup_tree(
        tree=tree, actor_id=test_actor_id, activity=test_activity
    )
    bt.setup()

    blackboard = py_trees.blackboard.Client(name="test")
    blackboard.register_key(key="activity", access=py_trees.common.Access.READ)

    assert blackboard.activity == test_activity


def test_setup_tree_with_context_data(bridge, test_actor_id):
    """Test blackboard populated with additional context data."""
    tree = AlwaysSucceed()
    context = {"report_id": "report-123", "case_id": "case-456"}

    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id, **context)
    bt.setup()

    blackboard = py_trees.blackboard.Client(name="test")
    blackboard.register_key(
        key="report_id", access=py_trees.common.Access.READ
    )
    blackboard.register_key(key="case_id", access=py_trees.common.Access.READ)

    assert blackboard.report_id == "report-123"
    assert blackboard.case_id == "case-456"


# Tests for execute_tree


def test_execute_tree_success(bridge, test_actor_id):
    """Test successful tree execution returns SUCCESS."""
    tree = AlwaysSucceed()
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    result = bridge.execute_tree(bt)

    assert isinstance(result, BTExecutionResult)
    assert result.status == Status.SUCCESS
    assert result.feedback_message == "Success"
    assert result.errors is None


def test_execute_tree_failure(bridge, test_actor_id):
    """Test failed tree execution returns FAILURE."""
    tree = AlwaysFail()
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    result = bridge.execute_tree(bt)

    assert result.status == Status.FAILURE
    assert result.feedback_message == "Failure"
    assert result.errors is None


def test_execute_tree_running_then_success(bridge, test_actor_id):
    """Test tree that runs multiple ticks before succeeding."""
    tree = RunNTimes(n=5)
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    result = bridge.execute_tree(bt)

    assert result.status == Status.SUCCESS
    assert "5 ticks" in result.feedback_message
    assert result.errors is None


def test_execute_tree_max_iterations(bridge, test_actor_id):
    """Test tree execution stops at max iterations."""
    tree = RunNTimes(n=200)  # Will never complete within default limit
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    result = bridge.execute_tree(bt, max_iterations=10)

    assert result.status == Status.FAILURE
    assert "exceeded max iterations" in result.feedback_message
    assert result.errors is not None
    assert len(result.errors) == 1


def test_execute_tree_with_exception(bridge, test_actor_id):
    """Test tree execution handles exceptions gracefully."""
    tree = ExceptionNode()
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    result = bridge.execute_tree(bt)

    assert result.status == Status.FAILURE
    assert "exception" in result.feedback_message.lower()
    assert result.errors is not None
    assert len(result.errors) == 1


def test_execute_tree_verifies_blackboard_access(bridge, test_actor_id):
    """Test tree can access blackboard data during execution."""
    tree = CheckBlackboard()
    bt = bridge.setup_tree(tree=tree, actor_id=test_actor_id)

    result = bridge.execute_tree(bt)

    assert result.status == Status.SUCCESS
    assert test_actor_id in result.feedback_message


# Tests for execute_with_setup (convenience method)


def test_execute_with_setup_success(bridge, test_actor_id):
    """Test convenience method for setup + execution."""
    tree = AlwaysSucceed()

    result = bridge.execute_with_setup(tree=tree, actor_id=test_actor_id)

    assert result.status == Status.SUCCESS
    assert result.errors is None


def test_execute_with_setup_with_activity(bridge, test_actor_id):
    """Test convenience method with activity parameter."""
    tree = AlwaysSucceed()
    test_activity = {"type": "Accept"}

    result = bridge.execute_with_setup(
        tree=tree, actor_id=test_actor_id, activity=test_activity
    )

    assert result.status == Status.SUCCESS


def test_execute_with_setup_with_context(bridge, test_actor_id):
    """Test convenience method with additional context."""
    tree = CheckBlackboard()

    result = bridge.execute_with_setup(
        tree=tree, actor_id=test_actor_id, report_id="test-report"
    )

    assert result.status == Status.SUCCESS


def test_execute_with_setup_custom_max_iterations(bridge, test_actor_id):
    """Test convenience method respects max_iterations parameter."""
    tree = RunNTimes(n=50)

    result = bridge.execute_with_setup(
        tree=tree, actor_id=test_actor_id, max_iterations=10
    )

    assert result.status == Status.FAILURE
    assert "exceeded max iterations" in result.feedback_message


# Integration tests


def test_bridge_isolates_actor_executions(bridge, datalayer):
    """Test multiple actors have isolated BT executions."""
    actor1 = "https://example.org/actor1"
    actor2 = "https://example.org/actor2"

    result1 = bridge.execute_with_setup(
        tree=CheckBlackboard(), actor_id=actor1, custom_data="actor1-data"
    )

    result2 = bridge.execute_with_setup(
        tree=CheckBlackboard(), actor_id=actor2, custom_data="actor2-data"
    )

    # Both should succeed independently
    assert result1.status == Status.SUCCESS
    assert actor1 in result1.feedback_message

    assert result2.status == Status.SUCCESS
    assert actor2 in result2.feedback_message


def test_bridge_sequential_executions(bridge, test_actor_id):
    """Test multiple sequential BT executions work correctly."""
    results = []

    for i in range(3):
        tree = AlwaysSucceed(name=f"Test-{i}")
        result = bridge.execute_with_setup(tree=tree, actor_id=test_actor_id)
        results.append(result)

    # All should succeed
    assert all(r.status == Status.SUCCESS for r in results)
    assert len(results) == 3
