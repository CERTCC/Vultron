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

"""Action nodes for SenderSideBT."""

from typing import Callable

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.use_cases._helpers import _resolve_case_manager_id
from vultron.core.use_cases._helpers import add_activity_to_outbox


class ResolveCaseManagerNode(DataLayerActionWithPorts):
    """Look up the CASE_MANAGER actor ID and write it to the blackboard."""

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "case_manager_id": PortInformation(
                data_type=str | None, required=True
            )
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_manager_id": "/case_manager_id"}

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            self._set_output("case_manager_id", None)  # BT-17-003
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case = self.datalayer.read_case(self.case_id)
        if case is None:
            self.feedback_message = (
                f"Case '{self.case_id}' not found or wrong type"
            )
            self._set_output("case_manager_id", None)  # BT-17-003
            return Status.FAILURE

        case_manager_id = _resolve_case_manager_id(case, self.datalayer)
        if case_manager_id is None:
            self.feedback_message = (
                f"No CASE_MANAGER participant found in case '{self.case_id}'"
            )
            self._set_output("case_manager_id", None)  # BT-17-003
            return Status.FAILURE

        self._set_output("case_manager_id", case_manager_id)
        self.logger.debug(
            "Resolved CASE_MANAGER actor for case '%s'", self.case_id
        )
        return Status.SUCCESS


class ConstructActivitiesNode(DataLayerActionWithPorts):
    """Build outbound AS2 activities and write their IDs to the blackboard."""

    def __init__(
        self,
        activity_builder: Callable[[str], list[str]],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._activity_builder = activity_builder

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_manager_id"] = PortInformation(
            data_type=str, required=True
        )
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "activity_ids": PortInformation(data_type=object, required=True)
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_manager_id": "/case_manager_id",
            "activity_ids": "/activity_ids",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_manager_id_bb: str = self.get_input("case_manager_id")

    def update(self) -> Status:
        case_manager_id = self.case_manager_id_bb
        if not case_manager_id:
            self.feedback_message = "case_manager_id not in blackboard"
            self._set_output("activity_ids", None)  # BT-17-003
            return Status.FAILURE

        try:
            activity_ids = self._activity_builder(case_manager_id)
        except Exception as exc:
            self.feedback_message = f"Activity construction failed: {exc}"
            self.logger.error(self.feedback_message)
            self._set_output("activity_ids", None)  # BT-17-003
            return Status.FAILURE

        self._set_output("activity_ids", activity_ids)
        self.logger.debug(
            "Constructed %d outbound activity/activities", len(activity_ids)
        )
        return Status.SUCCESS


class QueueToOutboxNode(DataLayerActionWithPorts):
    """Queue each activity ID from the blackboard to the actor's outbox."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["activity_ids"] = PortInformation(
            data_type=object, required=True
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity_ids": "/activity_ids"}

    def initialise(self) -> None:
        super().initialise()
        self.activity_ids: list[str] = self.get_input("activity_ids")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        activity_ids = self.activity_ids
        if activity_ids is None:
            self.feedback_message = "activity_ids not in blackboard"
            return Status.FAILURE

        try:
            dl = self.datalayer
            for activity_id in activity_ids:
                add_activity_to_outbox(
                    self.actor_id,
                    activity_id,
                    dl,  # type: ignore[arg-type]
                )
        except Exception as exc:
            self.feedback_message = (
                f"Failed to queue activity to outbox: {exc}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        self.logger.info(
            "Queued %d activity/activities to outbox for actor '%s'",
            len(activity_ids),
            self.actor_id,
        )
        return Status.SUCCESS
