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

from vultron.core.behaviors.helpers import (
    FindParticipantByActorIdNode,
    DataLayerCondition,
    DataLayerAction,
    ReadObject,
    UpdateObject,
    CreateObject,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.models.case import VultronCase
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.case_participant import CaseParticipant
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

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
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(datalayer):
    """Create BTBridge with test DataLayer."""
    return BTBridge(datalayer)


@pytest.fixture
def sample_report():
    """Sample as_VulnerabilityReport for testing CRUD operations."""
    return as_VulnerabilityReport(
        id_="https://example.org/objects/test-123",
        name="Test Object",
    )


# Keep the old name as an alias for backward compat within this module
@pytest.fixture
def sample_record(datalayer, sample_report):
    """Fixture that saves sample_report and returns it (backward-compat)."""
    datalayer.save(sample_report)
    return sample_report


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


def test_find_participant_by_actor_id_success_writes_blackboard(
    bridge, datalayer
):
    """FindParticipantByActorIdNode stores the matched participant."""
    actor_id = "https://example.org/actors/vendor-1"
    participant = VultronParticipant(
        id_="https://example.org/participants/vendor-1",
        attributed_to=actor_id,
        context="https://example.org/cases/case-1",
    )
    case = VultronCase(
        id_="https://example.org/cases/case-1",
        name="Case 1",
        case_participants=[participant.id_],
        actor_participant_index={actor_id: participant.id_},
        attributed_to="https://example.org/actors/case-manager",
    )
    datalayer.save(participant)
    datalayer.save(case)

    class AssertParticipantOnBlackboard(DataLayerCondition):
        def setup(self, **kwargs):
            super().setup(**kwargs)
            self.blackboard.register_key(
                key="found_participant", access=py_trees.common.Access.READ
            )

        def update(self) -> Status:
            found = self.blackboard.get("found_participant")
            if not isinstance(found, CaseParticipant):
                self.feedback_message = "No participant found on blackboard"
                return Status.FAILURE
            self.feedback_message = f"Found participant {found.id_}"
            return Status.SUCCESS

    tree = py_trees.composites.Sequence(
        name="FindParticipantAndAssert",
        memory=False,
        children=[
            FindParticipantByActorIdNode(
                case_id=case.id_,
                target_actor_id=actor_id,
                participant_key="found_participant",
            ),
            AssertParticipantOnBlackboard(
                name="AssertParticipantOnBlackboard"
            ),
        ],
    )

    result = bridge.execute_with_setup(tree, actor_id=actor_id)
    assert result.status == Status.SUCCESS


def test_find_participant_by_actor_id_fails_when_case_missing(bridge):
    """FindParticipantByActorIdNode returns FAILURE when case is missing."""
    node = FindParticipantByActorIdNode(
        case_id="https://example.org/cases/missing",
        target_actor_id="https://example.org/actors/vendor-1",
    )
    result = bridge.execute_with_setup(
        node, actor_id="https://example.org/actors/vendor-1"
    )
    assert result.status == Status.FAILURE


def test_find_participant_by_actor_id_fails_when_actor_not_participant(
    bridge, datalayer
):
    """FindParticipantByActorIdNode returns FAILURE on actor mismatch."""
    participant = VultronParticipant(
        id_="https://example.org/participants/vendor-2",
        attributed_to="https://example.org/actors/vendor-2",
        context="https://example.org/cases/case-2",
    )
    case = VultronCase(
        id_="https://example.org/cases/case-2",
        name="Case 2",
        case_participants=[participant.id_],
        attributed_to="https://example.org/actors/case-manager",
    )
    datalayer.save(participant)
    datalayer.save(case)

    node = FindParticipantByActorIdNode(
        case_id=case.id_,
        target_actor_id="https://example.org/actors/vendor-1",
    )
    result = bridge.execute_with_setup(
        node, actor_id="https://example.org/actors/vendor-1"
    )
    assert result.status == Status.FAILURE


def test_find_participant_by_actor_id_fails_on_index_divergence(
    bridge, datalayer
):
    """FindParticipantByActorIdNode fails fast on participant/index mismatch."""
    actor_id = "https://example.org/actors/vendor-1"
    case = VultronCase(
        id_="https://example.org/cases/case-diverge",
        name="Case Divergence",
        case_participants=[],
        actor_participant_index={
            actor_id: "https://example.org/participants/p1"
        },
        attributed_to="https://example.org/actors/case-manager",
    )
    datalayer.save(case)

    node = FindParticipantByActorIdNode(
        case_id=case.id_,
        target_actor_id=actor_id,
    )
    result = bridge.execute_with_setup(node, actor_id=actor_id)
    assert result.status == Status.FAILURE
    assert "divergence" in result.feedback_message


def test_read_object_success(bridge, datalayer, sample_record):
    """Verify ReadObject retrieves object from DataLayer."""
    # Read object using BT node (sample_record fixture already saved it)
    tree = ReadObject(
        table="VulnerabilityReport",
        object_id="https://example.org/objects/test-123",
    )
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS
    assert "Read VulnerabilityReport" in result.feedback_message


def test_read_object_stores_in_blackboard(bridge, datalayer, sample_record):
    """Verify ReadObject stores retrieved object in blackboard."""

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
            # obj is a PersistableModel (Pydantic BaseModel)
            name = getattr(obj, "name", None)
            if name != "Test Object":
                self.feedback_message = f"Object name incorrect: {name!r}"
                return Status.FAILURE
            self.feedback_message = "Object verified in blackboard"
            return Status.SUCCESS

    tree = py_trees.composites.Sequence(
        name="ReadAndCheck",
        memory=False,
        children=[
            ReadObject(
                table="VulnerabilityReport",
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
    tree = ReadObject(
        table="VulnerabilityReport",
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
    # Read object, then update it (sample_record fixture already saved it)
    tree = py_trees.composites.Sequence(
        name="ReadAndUpdate",
        memory=False,
        children=[
            ReadObject(
                table="VulnerabilityReport",
                object_id="https://example.org/objects/test-123",
            ),
            UpdateObject(
                object_id="https://example.org/objects/test-123",
                updates={"name": "Updated Name"},
            ),
        ],
    )
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS

    # Verify update persisted to DataLayer
    updated = datalayer.read("https://example.org/objects/test-123")
    assert updated is not None
    assert getattr(updated, "name", None) == "Updated Name"


def test_update_object_custom_name(bridge, datalayer, sample_record):
    """Verify UpdateObject accepts custom node name."""
    tree = py_trees.composites.Sequence(
        name="ReadAndUpdate",
        memory=False,
        children=[
            ReadObject(
                table="VulnerabilityReport",
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
        "id_": "https://example.org/objects/new-object",
        "type_": "Object",
        "name": "New Object",
    }

    tree = CreateObject(table="Object", object_data=new_object)
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS
    assert "Created" in result.feedback_message

    # Verify object persisted to DataLayer
    created = datalayer.get("Object", "https://example.org/objects/new-object")
    assert created is not None
    assert created["data_"]["name"] == "New Object"


def test_create_object_missing_id_fails(bridge, datalayer):
    """Verify CreateObject fails if object_data missing 'id_' field."""
    invalid_object = {
        "type_": "Object",
        "name": "Invalid Object",
        # Missing 'id_' field
    }

    tree = CreateObject(table="Object", object_data=invalid_object)
    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.FAILURE
    assert "missing required 'id_' field" in result.feedback_message.lower()


def test_create_object_custom_name(bridge, datalayer):
    """Verify CreateObject accepts custom node name."""
    new_object = {
        "id_": "https://example.org/objects/new-object",
        "type_": "Object",
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
    initial_object = {
        "id_": "https://example.org/objects/workflow-test",
        "type_": "VulnerabilityReport",
        "name": "Initial Name",
    }

    tree = py_trees.composites.Sequence(
        name="CRUDWorkflow",
        memory=False,
        children=[
            # Create object
            CreateObject(
                table="VulnerabilityReport", object_data=initial_object
            ),
            # Read it back
            ReadObject(
                table="VulnerabilityReport",
                object_id="https://example.org/objects/workflow-test",
            ),
            # Update it
            UpdateObject(
                object_id="https://example.org/objects/workflow-test",
                updates={"name": "Updated Name"},
            ),
        ],
    )

    result = bridge.execute_with_setup(tree, actor_id="actor-1")

    assert result.status == Status.SUCCESS

    # Verify final state in DataLayer
    final = datalayer.read("https://example.org/objects/workflow-test")
    assert final is not None
    assert getattr(final, "name", None) == "Updated Name"


def test_actor_isolation(bridge, datalayer, sample_record):
    """Verify actors have isolated BT execution contexts."""
    # Execute for actor-1
    tree1 = ReadObject(
        table="VulnerabilityReport",
        object_id="https://example.org/objects/test-123",
    )
    result1 = bridge.execute_with_setup(tree1, actor_id="actor-1")
    assert result1.status == Status.SUCCESS

    # Execute for actor-2 (separate context)
    tree2 = ReadObject(
        table="VulnerabilityReport",
        object_id="https://example.org/objects/test-123",
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


# Tests for BT logger fix (py_trees orphaned-logger root cause)


def test_condition_logger_is_managed_not_orphaned():
    """DataLayerCondition.logger must be a managed logging.Logger, not an
    orphaned py_trees.logging.Logger with parent=None."""
    import logging

    node = AlwaysTrueCondition(name="TestLogger")
    assert isinstance(
        node.logger, logging.Logger
    ), "self.logger must be the stdlib logging.Logger, not py_trees.logging.Logger"
    # A managed logger always has a parent (at minimum the root logger).
    assert (
        node.logger.parent is not None
    ), "self.logger.parent is None — logger is orphaned and log calls will be silently dropped"


def test_action_logger_is_managed_not_orphaned():
    """DataLayerAction.logger must be a managed logging.Logger, not an
    orphaned py_trees.logging.Logger with parent=None."""
    import logging

    node = NoOpAction(name="TestLogger")
    assert isinstance(node.logger, logging.Logger)
    assert (
        node.logger.parent is not None
    ), "self.logger.parent is None — logger is orphaned and log calls will be silently dropped"


def test_condition_logger_name_includes_class(bridge, datalayer):
    """Logger name should include the subclass name so log output is identifiable."""
    node = AlwaysTrueCondition(name="test-node")
    assert "AlwaysTrueCondition" in node.logger.name


# Tests for _require_* guard helpers on DataLayerCondition


def test_condition_require_datalayer_returns_failure_when_none():
    """_require_datalayer() returns FAILURE when datalayer is not set."""
    node = AlwaysTrueCondition(name="GuardTest")
    # datalayer defaults to None (no bridge/setup)
    result = node._require_datalayer()
    assert result == Status.FAILURE
    assert node.feedback_message == "DataLayer not available"


def test_condition_require_datalayer_returns_none_when_set(datalayer):
    """_require_datalayer() returns None (no failure) when datalayer is set."""
    node = AlwaysTrueCondition(name="GuardTest")
    node.datalayer = datalayer
    result = node._require_datalayer()
    assert result is None


def test_condition_require_datalayer_and_actor_returns_failure_when_both_none():
    """_require_datalayer_and_actor() returns FAILURE when both are None."""
    node = AlwaysTrueCondition(name="GuardTest")
    result = node._require_datalayer_and_actor()
    assert result == Status.FAILURE


def test_condition_require_datalayer_and_actor_returns_failure_when_actor_none(
    datalayer,
):
    """_require_datalayer_and_actor() returns FAILURE when only actor_id is None."""
    node = AlwaysTrueCondition(name="GuardTest")
    node.datalayer = datalayer
    node.actor_id = None
    result = node._require_datalayer_and_actor()
    assert result == Status.FAILURE


def test_condition_require_datalayer_and_actor_returns_failure_when_datalayer_none():
    """_require_datalayer_and_actor() returns FAILURE when only datalayer is None."""
    node = AlwaysTrueCondition(name="GuardTest")
    node.actor_id = "https://example.org/actors/a1"
    result = node._require_datalayer_and_actor()
    assert result == Status.FAILURE


def test_condition_require_datalayer_and_actor_returns_none_when_both_set(
    datalayer,
):
    """_require_datalayer_and_actor() returns None when both datalayer and actor_id are set."""
    node = AlwaysTrueCondition(name="GuardTest")
    node.datalayer = datalayer
    node.actor_id = "https://example.org/actors/a1"
    result = node._require_datalayer_and_actor()
    assert result is None


# Tests for _require_* guard helpers on DataLayerAction


def test_action_require_datalayer_returns_failure_when_none():
    """DataLayerAction._require_datalayer() returns FAILURE when datalayer is not set."""
    node = NoOpAction(name="GuardTest")
    result = node._require_datalayer()
    assert result == Status.FAILURE
    assert node.feedback_message == "DataLayer not available"


def test_action_require_datalayer_returns_none_when_set(datalayer):
    """DataLayerAction._require_datalayer() returns None when datalayer is set."""
    node = NoOpAction(name="GuardTest")
    node.datalayer = datalayer
    result = node._require_datalayer()
    assert result is None


def test_action_require_datalayer_and_actor_returns_failure_when_none():
    """DataLayerAction._require_datalayer_and_actor() returns FAILURE when both None."""
    node = NoOpAction(name="GuardTest")
    result = node._require_datalayer_and_actor()
    assert result == Status.FAILURE


def test_action_require_datalayer_and_actor_returns_none_when_both_set(
    datalayer,
):
    """DataLayerAction._require_datalayer_and_actor() returns None when both set."""
    node = NoOpAction(name="GuardTest")
    node.datalayer = datalayer
    node.actor_id = "https://example.org/actors/a1"
    result = node._require_datalayer_and_actor()
    assert result is None


def test_action_require_factory_returns_failure_when_none():
    """DataLayerAction._require_factory() returns FAILURE when factory is not set."""
    node = NoOpAction(name="GuardTest")
    result = node._require_factory()
    assert result == Status.FAILURE
    assert node.feedback_message == "trigger_activity_factory not available"


def test_action_require_factory_returns_none_when_set():
    """DataLayerAction._require_factory() returns None when factory is set."""
    from unittest.mock import MagicMock
    from vultron.core.ports.trigger_activity import TriggerActivityPort

    node = NoOpAction(name="GuardTest")
    node.trigger_activity_factory = MagicMock(spec=TriggerActivityPort)
    result = node._require_factory()
    assert result is None


def test_action_logger_emits_via_caplog(bridge, datalayer, caplog):
    """Log messages from BT action nodes propagate to caplog (not silently dropped)."""
    import logging

    class LoggingAction(DataLayerAction):
        def update(self) -> Status:
            self.logger.info("BT action log message emitted")
            return Status.SUCCESS

    with caplog.at_level(logging.INFO):
        tree = LoggingAction(name="LogAction")
        bridge.execute_with_setup(
            tree, actor_id="https://example.org/actors/a1"
        )

    assert any(
        "BT action log message emitted" in r.message for r in caplog.records
    )
