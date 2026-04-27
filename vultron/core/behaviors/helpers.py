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

"""
DataLayer-aware behavior tree helper nodes.

This module provides base classes and common nodes for BT implementations that
interact with the DataLayer for persistent state access.

Per specs/behavior-tree-integration.yaml:
- BT-07-001: BT nodes interact with DataLayer via Protocol interface
- BT-07-002: BT nodes use type-safe DataLayer wrappers
- BT-07-003: State transitions logged via DataLayer integration helpers
"""

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.models.protocols import has_outbox
from vultron.core.ports.datalayer import DataLayer, StorableRecord

logger = logging.getLogger(__name__)


class DataLayerCondition(py_trees.behaviour.Behaviour):
    """
    Base class for BT condition nodes that check state from DataLayer.

    Condition nodes check preconditions or state without side effects.
    Returns SUCCESS if condition holds, FAILURE otherwise.

    Subclasses should override update() to implement condition logic.
    """

    # Declare the managed logger type so subclass log calls are type-checked
    # against the stdlib logging.Logger API (not py_trees.logging.Logger).
    logger: logging.Logger  # type: ignore[assignment]

    def __init__(self, name: str):
        """
        Initialize condition node.

        Args:
            name: Descriptive name for this condition node
        """
        super().__init__(name=name)
        # py_trees creates self.logger = logging.Logger(name) with parent=None,
        # so messages are silently dropped.  Replace with a proper managed logger
        # so BT node log messages propagate through the standard logging hierarchy.
        self.logger = logging.getLogger(  # type: ignore[assignment]
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self.datalayer: DataLayer | None = None
        self.actor_id: str | None = None

    def setup(self, **kwargs: Any) -> None:
        """Set up blackboard access for DataLayer and actor_id."""
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(
            key="datalayer", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="actor_id", access=py_trees.common.Access.READ
        )

    def initialise(self) -> None:
        """Initialize condition node by reading blackboard state."""
        self.datalayer = self.blackboard.datalayer
        self.actor_id = self.blackboard.actor_id

        if self.datalayer is None:
            self.logger.error(
                f"{self.name}: DataLayer not found in blackboard"
            )
        if self.actor_id is None:
            self.logger.error(f"{self.name}: actor_id not found in blackboard")

    def update(self) -> Status:
        """
        Evaluate condition. Override in subclasses.

        Returns:
            SUCCESS if condition holds, FAILURE otherwise
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.update() must be implemented by subclass"
        )


class DataLayerAction(py_trees.behaviour.Behaviour):
    """
    Base class for BT action nodes that modify state in DataLayer.

    Action nodes perform state transitions with side effects.
    Returns SUCCESS if action completes, FAILURE if action fails.

    Subclasses should override update() to implement action logic.
    """

    # Declare the managed logger type so subclass log calls are type-checked
    # against the stdlib logging.Logger API (not py_trees.logging.Logger).
    logger: logging.Logger  # type: ignore[assignment]

    def __init__(self, name: str):
        """
        Initialize action node.

        Args:
            name: Descriptive name for this action node
        """
        super().__init__(name=name)
        # py_trees creates self.logger = logging.Logger(name) with parent=None,
        # so messages are silently dropped.  Replace with a proper managed logger
        # so BT node log messages propagate through the standard logging hierarchy.
        self.logger = logging.getLogger(  # type: ignore[assignment]
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self.datalayer: DataLayer | None = None
        self.actor_id: str | None = None

    def setup(self, **kwargs: Any) -> None:
        """Set up blackboard access for DataLayer and actor_id."""
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(
            key="datalayer", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="actor_id", access=py_trees.common.Access.READ
        )

    def initialise(self) -> None:
        """Initialize action node by reading blackboard state."""
        self.datalayer = self.blackboard.datalayer
        self.actor_id = self.blackboard.actor_id

        if self.datalayer is None:
            self.logger.error(
                f"{self.name}: DataLayer not found in blackboard"
            )
        if self.actor_id is None:
            self.logger.error(f"{self.name}: actor_id not found in blackboard")

    def update(self) -> Status:
        """
        Perform action. Override in subclasses.

        Returns:
            SUCCESS if action completes, FAILURE if action fails
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.update() must be implemented by subclass"
        )


class ReadObject(DataLayerCondition):
    """
    Read an object from DataLayer and store in blackboard.

    Returns SUCCESS if object found and stored, FAILURE if not found.
    Stores retrieved object in blackboard with key "object_{last_path_segment}".
    """

    def __init__(self, table: str, object_id: str, name: str | None = None):
        """
        Initialize ReadObject node.

        Args:
            table: DataLayer table name to read from
            object_id: ID of object to retrieve
            name: Optional custom name (defaults to "ReadObject_{table}_{last_segment}")
        """
        # Use last part of ID for blackboard key (URL-safe)
        self.blackboard_key = f"object_{object_id.split('/')[-1]}"
        display_name = name or f"ReadObject_{table}_{object_id.split('/')[-1]}"
        super().__init__(name=display_name)
        self.table = table
        self.object_id = object_id

    def setup(self, **kwargs: Any) -> None:
        """Set up blackboard access including output key for retrieved object."""
        super().setup(**kwargs)
        # Register key for storing retrieved object (use WRITE access)
        self.blackboard.register_key(
            key=self.blackboard_key, access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        """
        Read object from DataLayer and store in blackboard.

        Returns:
            SUCCESS if object found, FAILURE if not found or error
        """
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        try:
            record = self.datalayer.get(self.table, self.object_id)

            if record is None:
                self.feedback_message = (
                    f"Object not found: {self.table}/{self.object_id}"
                )
                self.logger.debug(self.feedback_message)
                return Status.FAILURE

            # Store retrieved object in blackboard with simplified key
            setattr(self.blackboard, self.blackboard_key, record)
            self.feedback_message = f"Read {self.table}/{self.object_id}"
            self.logger.debug(self.feedback_message)
            return Status.SUCCESS

        except Exception as e:
            self.feedback_message = (
                f"Error reading {self.table}/{self.object_id}: {e}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE


class UpdateObject(DataLayerAction):
    """
    Update an object in DataLayer with new values.

    Reads current object from blackboard (stored by ReadObject), applies updates, and persists.
    Returns SUCCESS if update completes, FAILURE if error occurs.
    """

    def __init__(
        self,
        object_id: str,
        updates: dict[str, Any],
        name: str | None = None,
    ):
        """
        Initialize UpdateObject node.

        Args:
            object_id: ID of object to update
            updates: Dictionary of field updates to apply
            name: Optional custom name (defaults to "UpdateObject_{last_segment}")
        """
        # Use last part of ID for blackboard key (URL-safe)
        self.blackboard_key = f"object_{object_id.split('/')[-1]}"
        display_name = name or f"UpdateObject_{object_id.split('/')[-1]}"
        super().__init__(name=display_name)
        self.object_id = object_id
        self.updates = updates

    def setup(self, **kwargs: Any) -> None:
        """Set up blackboard access including object key for reading."""
        super().setup(**kwargs)
        # Register key for reading object to update
        self.blackboard.register_key(
            key=self.blackboard_key, access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        """
        Update object in DataLayer.

        Returns:
            SUCCESS if update completes, FAILURE if error occurs
        """
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        try:
            # Try to read current record from blackboard
            # py_trees will raise KeyError if key not written to yet
            try:
                current_dict = self.blackboard.get(self.blackboard_key)
            except KeyError:
                self.feedback_message = (
                    f"Object not in blackboard: {self.object_id}"
                )
                self.logger.error(self.feedback_message)
                return Status.FAILURE

            if current_dict is None:
                self.feedback_message = (
                    f"Object not in blackboard: {self.object_id}"
                )
                self.logger.error(self.feedback_message)
                return Status.FAILURE

            # Build an updated StorableRecord without importing the adapter-layer Record.
            if "data_" in current_dict:
                updated_data = {**current_dict["data_"], **self.updates}
                storable = StorableRecord(
                    id_=current_dict["id_"],
                    type_=current_dict["type_"],
                    data_=updated_data,
                )
            else:
                updated_data = {**current_dict, **self.updates}
                record_type = updated_data.get("type_", "Object")
                storable = StorableRecord(
                    id_=self.object_id,
                    type_=record_type,
                    data_=updated_data,
                )

            # Persist to DataLayer
            self.datalayer.update(self.object_id, storable)

            self.feedback_message = (
                f"Updated {self.object_id} with {len(self.updates)} fields"
            )
            self.logger.info(self.feedback_message)
            return Status.SUCCESS

        except Exception as e:
            self.feedback_message = f"Error updating {self.object_id}: {e}"
            self.logger.error(self.feedback_message)
            return Status.FAILURE


class CreateObject(DataLayerAction):
    """
    Create a new object in DataLayer.

    Creates object from provided data and persists to DataLayer.
    Returns SUCCESS if creation completes, FAILURE if error occurs.
    """

    def __init__(
        self,
        table: str,
        object_data: dict,
        name: str | None = None,
    ):
        """
        Initialize CreateObject node.

        Args:
            table: DataLayer table name to create object in
            object_data: Data dict for new object (must include 'id_' field)
            name: Optional custom name (defaults to "CreateObject_{table}")
        """
        display_name = name or f"CreateObject_{table}"
        super().__init__(name=display_name)
        self.table = table
        self.object_data = object_data

    def update(self) -> Status:
        """
        Create object in DataLayer.

        Returns:
            SUCCESS if creation completes, FAILURE if error occurs
        """
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        try:
            # Ensure object_data has required 'id_' field
            if "id_" not in self.object_data:
                self.feedback_message = (
                    "Object data missing required 'id_' field"
                )
                self.logger.error(self.feedback_message)
                return Status.FAILURE

            # Get type from data, default to table name
            object_type = self.object_data.get("type_", self.table)
            object_id = self.object_data["id_"]

            # Build a typed StorableRecord and pass it to the DataLayer
            storable = StorableRecord(
                id_=object_id,
                type_=object_type,
                data_=self.object_data,
            )

            # Create object in DataLayer
            self.datalayer.create(storable)

            self.feedback_message = f"Created {self.table}/{object_id}"
            self.logger.info(self.feedback_message)
            return Status.SUCCESS

        except Exception as e:
            self.feedback_message = (
                f"Error creating object in {self.table}: {e}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE


class UpdateActorOutbox(DataLayerAction):
    """
    Update actor's outbox with a new activity.

    Reads ``activity_id`` and ``case_id`` from the blackboard (set by the
    preceding activity-creation node) and appends the activity ID to the
    actor's outbox.  Also queues the activity for delivery via
    ``record_outbox_item``.

    Per BTND-04-001: defined here as shared logic used by both
    ``vultron/core/behaviors/report/nodes.py`` and
    ``vultron/core/behaviors/case/nodes.py``.
    """

    def __init__(self, name: str | None = None):
        """
        Initialize UpdateActorOutbox node.

        Args:
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        """Set up blackboard access including activity_id and case_id keys."""
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        """
        Update actor's outbox with activity ID.

        Returns:
            SUCCESS if outbox updated, FAILURE on error
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            activity_id = self.blackboard.get("activity_id")
            if activity_id is None:
                self.logger.error(
                    f"{self.name}: activity_id not found in blackboard"
                )
                return Status.FAILURE

            case_id = self.blackboard.get("case_id")

            actor_obj = self.datalayer.read(
                self.actor_id, raise_on_missing=True
            )

            if not has_outbox(actor_obj):
                self.logger.error(
                    f"{self.name}: Actor {self.actor_id} has no outbox"
                    " or outbox.items"
                )
                return Status.FAILURE

            actor_obj.outbox.items.append(activity_id)
            self.datalayer.save(actor_obj)

            self.datalayer.record_outbox_item(self.actor_id, activity_id)
            self.logger.info(
                "Queued Create(Case '%s') activity '%s' to actor '%s' outbox"
                " (case creation notification)",
                case_id,
                activity_id,
                self.actor_id,
            )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error updating actor outbox: {e}")
            return Status.FAILURE
