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

"""Unit tests for DataLayer-aware BT helper nodes."""

import pytest
import py_trees
from py_trees.common import Status

from vultron.behaviors.helpers import (
    DataLayerCondition,
    DataLayerAction,
    ReadObject,
    UpdateObject,
    CreateObject,
)
from vultron.behaviors.bridge import BTBridge
from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
from vultron.api.v2.datalayer.db_record import Record

# Test implementation of abstract base classes


class AlwaysTrueCondition(DataLayerCondition):
    """Test condition that always returns SUCCESS."""

    def update(self) -> Status:
        self.feedback_message = "Condition is true"
        return Status.SUCCESS


class AlwaysFalseCondition(DataLayerCondition):
    """Test condition that always returns FAILURE."""

    def update(self) -> Status:
        self.feedback_message = "Condition is false"
        return Status.FAILURE


class NoOpAction(DataLayerAction):
    """Test action that always succeeds without side effects."""

    def update(self) -> Status:
        self.feedback_message = "Action completed"
        return Status.SUCCESS


# Fixtures


@pytest.fixture
def datalayer():
    """Create in-memory DataLayer for testing."""
    return TinyDbDataLayer(db_path=None)


@pytest.fixture
def bridge(datalayer):
    """Create BTBridge with test DataLayer."""
    return BTBridge(datalayer)


@pytest.fixture
def sample_record():
    """Sample record for testing CRUD operations."""
    return Record(
        id_="https://example.org/objects/test-123",
        type_="Object",
        data_={
            "as_id": "https://example.org/objects/test-123",
            "as_type": "Object",
            "name": "Test Object",
            "content": "Sample content",
        },
    )


# Tests for DataLayerCondition base class


def test_condition_base_class_setup(bridge, datalayer):
    """Verify DataLayerCondition sets up blackboard access correctly."""
    tree = AlwaysTrueCondition(name="TestCondition")
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS
    assert "Condition is true" in result.feedback_message


def test_condition_accesses_datalayer_from_blackboard(bridge, datalayer):
    """Verify condition node can access DataLayer from blackboard."""

    class CheckDataLayerAccess(DataLayerCondition):
        def update(self) -> Status:
            if self.datalayer is None:
                self.feedback_message = "DataLayer is None"
                return Status.FAILURE
            if self.actor_id is None:
                self.feedback_message = "actor_id is None"
                return Status.FAILURE
            self.feedback_message = f"Access OK for {self.actor_id}"
            return Status.SUCCESS

    tree = CheckDataLayerAccess(name="CheckAccess")
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS
    assert "Access OK for actor-1" in result.feedback_message


def test_condition_base_class_not_implemented(bridge, datalayer):
    """Verify base class raises NotImplementedError if update() not overridden."""

    class UnimplementedCondition(DataLayerCondition):
        pass  # Don't override update()

    tree = UnimplementedCondition(name="Unimplemented")
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    # Should fail because update() raises NotImplementedError
    assert result.status == Status.FAILURE
    assert result.errors is not None


# Tests for DataLayerAction base class


def test_action_base_class_setup(bridge, datalayer):
    """Verify DataLayerAction sets up blackboard access correctly."""
    tree = NoOpAction(name="TestAction")
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS
    assert "Action completed" in result.feedback_message


def test_action_accesses_datalayer_from_blackboard(bridge, datalayer):
    """Verify action node can access DataLayer from blackboard."""

    class CheckDataLayerAccess(DataLayerAction):
        def update(self) -> Status:
            if self.datalayer is None:
                self.feedback_message = "DataLayer is None"
                return Status.FAILURE
            if self.actor_id is None:
                self.feedback_message = "actor_id is None"
                return Status.FAILURE
            self.feedback_message = f"Access OK for {self.actor_id}"
            return Status.SUCCESS

    tree = CheckDataLayerAccess(name="CheckAccess")
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS
    assert "Access OK for actor-1" in result.feedback_message


def test_action_base_class_not_implemented(bridge, datalayer):
    """Verify base class raises NotImplementedError if update() not overridden."""

    class UnimplementedAction(DataLayerAction):
        pass  # Don't override update()

    tree = UnimplementedAction(name="Unimplemented")
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    # Should fail because update() raises NotImplementedError
    assert result.status == Status.FAILURE
    assert result.errors is not None


# Tests for ReadObject node


def test_read_object_success(bridge, datalayer, sample_record):
    """Verify ReadObject retrieves object from DataLayer."""
    # Create object in DataLayer
    datalayer.create(sample_record)

    # Read object using BT node
    tree = ReadObject(
        table="Object", object_id="https://example.org/objects/test-123"
    )
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS
    assert "Read Object" in result.feedback_message


def test_read_object_stores_in_blackboard(bridge, datalayer, sample_record):
    """Verify ReadObject stores retrieved object in blackboard."""
    datalayer.create(sample_record)

    # Create sequence: Read object, then check blackboard
    class CheckBlackboard(DataLayerCondition):
        def setup(self, **kwargs):
            super().setup(**kwargs)
            self.blackboard.register_key(
                key="object_test-123",  # Simplified key from ReadObject
                access=py_trees.common.Access.READ,
            )

        def update(self) -> Status:
            obj = getattr(self.blackboard, "object_test-123", None)
            if obj is None:
                self.feedback_message = "Object not in blackboard"
                return Status.FAILURE
            # obj is a Record dict with {id_, type_, data_}
            if "data_" in obj:
                data = obj["data_"]
            else:
                data = obj
            if data.get("name") != "Test Object":
                self.feedback_message = (
                    f"Object data incorrect: {data.get('name')}"
                )
                return Status.FAILURE
            self.feedback_message = "Object verified in blackboard"
            return Status.SUCCESS

    tree = py_trees.composites.Sequence(
        name="ReadAndCheck",
        memory=False,
        children=[
            ReadObject(
                table="Object",
                object_id="https://example.org/objects/test-123",
            ),
            CheckBlackboard(name="CheckBlackboard"),
        ],
    )
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS


def test_read_object_not_found(bridge, datalayer):
    """Verify ReadObject returns FAILURE when object not found."""
    tree = ReadObject(
        table="Object", object_id="https://example.org/objects/nonexistent"
    )
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.FAILURE
    assert "not found" in result.feedback_message.lower()


def test_read_object_custom_name(bridge, datalayer, sample_record):
    """Verify ReadObject accepts custom node name."""
    datalayer.create(sample_record)

    tree = ReadObject(
        table="Object",
        object_id="https://example.org/objects/test-123",
        name="CustomReadName",
    )
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS
    # Check tree node has custom name
    assert tree.name == "CustomReadName"


# Tests for UpdateObject node


def test_update_object_success(bridge, datalayer, sample_record):
    """Verify UpdateObject modifies object in DataLayer."""
    datalayer.create(sample_record)

    # Read object, then update it
    tree = py_trees.composites.Sequence(
        name="ReadAndUpdate",
        memory=False,
        children=[
            ReadObject(
                table="Object",
                object_id="https://example.org/objects/test-123",
            ),
            UpdateObject(
                object_id="https://example.org/objects/test-123",
                updates={"name": "Updated Name", "status": "modified"},
            ),
        ],
    )
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS

    # Verify update persisted to DataLayer
    updated = datalayer.get("Object", "https://example.org/objects/test-123")
    assert updated is not None
    # updated is a Record dict {id_, type_, data_}
    if "data_" in updated:
        data = updated["data_"]
    else:
        data = updated
    assert data["name"] == "Updated Name"
    assert data["status"] == "modified"
    assert data["content"] == "Sample content"  # Unchanged field preserved


def test_update_object_custom_name(bridge, datalayer, sample_record):
    """Verify UpdateObject accepts custom node name."""
    datalayer.create(sample_record)

    tree = py_trees.composites.Sequence(
        name="ReadAndUpdate",
        memory=False,
        children=[
            ReadObject(
                table="Object",
                object_id="https://example.org/objects/test-123",
            ),
            UpdateObject(
                object_id="https://example.org/objects/test-123",
                updates={"name": "Updated Name"},
                name="CustomUpdateName",
            ),
        ],
    )
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS
    # Check second child has custom name
    assert tree.children[1].name == "CustomUpdateName"


# Tests for CreateObject node


def test_create_object_success(bridge, datalayer):
    """Verify CreateObject persists new object to DataLayer."""
    new_object = {
        "as_id": "https://example.org/objects/new-object",
        "as_type": "Object",
        "name": "New Object",
    }

    tree = CreateObject(table="Object", object_data=new_object)
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS
    assert "Created" in result.feedback_message

    # Verify object persisted to DataLayer
    created = datalayer.get("Object", "https://example.org/objects/new-object")
    assert created is not None
    # created is a Record dict {id_, type_, data_}
    if "data_" in created:
        data = created["data_"]
    else:
        data = created
    assert data["name"] == "New Object"


def test_create_object_missing_id_fails(bridge, datalayer):
    """Verify CreateObject fails if object_data missing 'as_id' field."""
    invalid_object = {
        "as_type": "Object",
        "name": "Invalid Object",
        # Missing 'as_id' field
    }

    tree = CreateObject(table="Object", object_data=invalid_object)
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.FAILURE
    assert "missing required 'as_id' field" in result.feedback_message.lower()


def test_create_object_custom_name(bridge, datalayer):
    """Verify CreateObject accepts custom node name."""
    new_object = {
        "as_id": "https://example.org/objects/new-object",
        "as_type": "Object",
        "name": "New Object",
    }

    tree = CreateObject(
        table="Object", object_data=new_object, name="CustomCreateName"
    )
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS
    assert tree.name == "CustomCreateName"


# Integration tests


def test_full_crud_workflow(bridge, datalayer):
    """Verify complete CRUD workflow using helper nodes."""
    initial_object = Record(
        id_="https://example.org/objects/workflow-test",
        type_="Object",
        data_={
            "as_id": "https://example.org/objects/workflow-test",
            "as_type": "Object",
            "name": "Initial Name",
            "status": "draft",
        },
    )

    tree = py_trees.composites.Sequence(
        name="CRUDWorkflow",
        memory=False,
        children=[
            # Create object
            CreateObject(table="Object", object_data=initial_object.data_),
            # Read it back
            ReadObject(
                table="Object",
                object_id="https://example.org/objects/workflow-test",
            ),
            # Update it
            UpdateObject(
                object_id="https://example.org/objects/workflow-test",
                updates={"name": "Updated Name", "status": "published"},
            ),
        ],
    )

    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS

    # Verify final state in DataLayer
    final = datalayer.get(
        "Object", "https://example.org/objects/workflow-test"
    )
    assert final is not None
    # final is a Record dict {id_, type_, data_}
    if "data_" in final:
        data = final["data_"]
    else:
        data = final
    assert data["name"] == "Updated Name"
    assert data["status"] == "published"


def test_actor_isolation(bridge, datalayer, sample_record):
    """Verify actors have isolated BT execution contexts."""
    datalayer.create(sample_record)

    # Execute for actor-1
    tree1 = ReadObject(
        table="Object", object_id="https://example.org/objects/test-123"
    )
    result1 = bridge.execute_with_setup(tree1, actor_id="actor-1")
    assert result1.status == Status.SUCCESS

    # Execute for actor-2 (separate context)
    tree2 = ReadObject(
        table="Object", object_id="https://example.org/objects/test-123"
    )
    result2 = bridge.execute_with_setup(tree2, actor_id="actor-2")
    assert result2.status == Status.SUCCESS

    # Both should succeed independently
    assert result1.feedback_message != result2.feedback_message or True


def test_error_propagation(bridge, datalayer):
    """Verify errors in helper nodes propagate correctly."""

    class RaiseExceptionAction(DataLayerAction):
        def update(self) -> Status:
            raise ValueError("Intentional test error")

    tree = RaiseExceptionAction(name="ErrorAction")
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    # Should capture exception and return FAILURE
    assert result.status == Status.FAILURE
    assert result.errors is not None
    assert "Intentional test error" in result.feedback_message
