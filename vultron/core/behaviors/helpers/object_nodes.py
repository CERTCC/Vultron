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

"""Generic read, update and create BT nodes over the DataLayer.

The legacy record-level nodes HP-08-001 names as the one retained
compatibility use in core.
"""

from typing import Any, cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation
from pydantic import BaseModel

from vultron.core.behaviors.helpers.base import DataLayerAction
from vultron.core.behaviors.helpers.ports_base import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.node_logger import port_wiring_logger
from vultron.core.ports.datalayer import DataLayer, StorableRecord


class ReadObject(DataLayerConditionWithPorts):
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
        self.blackboard_key = f"object_{object_id.rsplit('/', maxsplit=1)[-1]}"
        display_name = (
            name
            or f"ReadObject_{table}_{object_id.rsplit('/', maxsplit=1)[-1]}"
        )
        super().__init__(name=display_name)
        self.table = table
        self.object_id = object_id

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "object_data": PortInformation(data_type=object, required=True),
    }

    def setup(self, **kwargs: Any) -> None:
        self.setup_ports(
            port_remappings={
                "datalayer": "/datalayer",
                "actor_id": "/actor_id",
                "object_data": f"/{self.blackboard_key}",
            },
            logger=port_wiring_logger(),
        )

    def update(self) -> Status:
        """
        Read object from DataLayer and store in blackboard.

        Returns:
            SUCCESS if object found, FAILURE if not found or error
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        try:
            record = self.datalayer.read(self.object_id)

            if record is None:
                self.feedback_message = (
                    f"Object not found: {self.table}/{self.object_id}"
                )
                self.logger.debug("%s", self.feedback_message)
                return Status.FAILURE

            self._set_output("object_data", record)
            self.feedback_message = f"Read {self.table}/{self.object_id}"
            self.logger.debug("%s", self.feedback_message)
            return Status.SUCCESS

        except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
            self.feedback_message = (
                f"Error reading {self.table}/{self.object_id}: {e}"
            )
            self.logger.error("%s", self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE


class UpdateObject(DataLayerActionWithPorts):
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
        self.blackboard_key = f"object_{object_id.rsplit('/', maxsplit=1)[-1]}"
        display_name = (
            name or f"UpdateObject_{object_id.rsplit('/', maxsplit=1)[-1]}"
        )
        super().__init__(name=display_name)
        self.object_id = object_id
        self.updates = updates

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "object_data": PortInformation(data_type=object, required=True),
    }

    def setup(self, **kwargs: Any) -> None:
        self.setup_ports(
            port_remappings={
                "datalayer": "/datalayer",
                "actor_id": "/actor_id",
                "trigger_activity_factory": "/trigger_activity_factory",
                "object_data": f"/{self.blackboard_key}",
            },
            logger=port_wiring_logger(),
        )

    def initialise(self) -> None:
        super().initialise()
        try:
            self._current_dict = self.get_input("object_data")
        except (NoDataAvailable, NotImplementedError):
            self._current_dict = None

    def update(self) -> Status:
        """
        Update object in DataLayer.

        Returns:
            SUCCESS if update completes, FAILURE if error occurs
        """
        if (f := self._require_datalayer()) is not None:
            return f

        try:
            current_dict = self._current_dict

            if current_dict is None:
                self.feedback_message = (
                    f"Object not in blackboard: {self.object_id}"
                )
                self.logger.error("%s", self.feedback_message)
                return Status.FAILURE

            # Build an updated StorableRecord without importing the adapter-layer Record.
            if isinstance(current_dict, BaseModel):
                # Typed domain object stored by ReadObject; serialise to dict
                # before applying updates.
                current_data = current_dict.model_dump(mode="json")
                record_type = current_data.get("type_") or str(
                    getattr(current_dict, "type_", "Object")
                )
                updated_data = {**current_data, **self.updates}
                storable = StorableRecord(
                    id_=self.object_id,
                    type_=record_type,
                    data_=updated_data,
                )
            elif "data_" in current_dict:
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

            # Persist to DataLayer; update() is a low-level primitive not in
            # CasePersistence — cast to the full DataLayer contract here.
            cast(DataLayer, self.datalayer).update(self.object_id, storable)

            self.feedback_message = (
                f"Updated {self.object_id} with {len(self.updates)} fields"
            )
            self.logger.info("%s", self.feedback_message)
            return Status.SUCCESS

        except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
            self.feedback_message = f"Error updating {self.object_id}: {e}"
            self.logger.error("%s", self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
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
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        try:
            # Ensure object_data has required 'id_' field
            if "id_" not in self.object_data:
                self.feedback_message = (
                    "Object data missing required 'id_' field"
                )
                self.logger.error("%s", self.feedback_message)
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
            self.logger.info("%s", self.feedback_message)
            return Status.SUCCESS

        except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
            self.feedback_message = (
                f"Error creating object in {self.table}: {e}"
            )
            self.logger.error("%s", self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE
