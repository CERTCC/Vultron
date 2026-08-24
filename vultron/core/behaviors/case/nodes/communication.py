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
Communication action nodes for case behavior trees.

Provides action nodes that emit outbound activities related to case creation.

Composite subtrees assembling these leaf nodes are defined in the sibling
``communication_tree.py`` module at the process-area root per BTND-07-003:

- ``EmitCreateCaseActivity``

Delegation-related nodes (``AutoAcceptCaseParticipantRoleNode``,
``EmitRejectCaseParticipantRoleNode``) live in the sibling ``delegation.py``
module.
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.vultron_types import VultronCreateCaseActivity

logger = logging.getLogger(__name__)


class CollectCaseAddresseesNode(DataLayerActionWithPorts):
    """Resolve case object and peer addressees for Create(Case) emission."""

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=True)
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "create_case_obj": PortInformation(
                data_type=object, required=True
            ),
            "create_case_addressees": PortInformation(
                data_type=object, required=True
            ),
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "create_case_obj": "/create_case_obj",
            "create_case_addressees": "/create_case_addressees",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        case_id = self.case_id_bb
        if not isinstance(case_id, str):
            self.logger.error(
                f"{self.name}: case_id must be a string, got {type(case_id)}"
            )
            return Status.FAILURE

        case_obj = self.datalayer.read(case_id)
        if isinstance(case_obj, VulnerabilityCase):
            addressees = [
                actor_id
                for actor_id in case_obj.actor_participant_index.keys()
                if actor_id != self.actor_id
            ]
        else:
            addressees = []

        if addressees:
            self.logger.info(
                f"{self.name}: Notifying addressees: {addressees}"
            )

        self._set_output("create_case_obj", case_obj)
        self._set_output("create_case_addressees", addressees)
        return Status.SUCCESS


class CreateAndPersistCaseActivityNode(DataLayerActionWithPorts):
    """Build and persist Create(Case), then publish activity_id to blackboard."""

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=True)
        ports["create_case_obj"] = PortInformation(
            data_type=object, required=True
        )
        ports["create_case_addressees"] = PortInformation(
            data_type=object, required=True
        )
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {"activity_id": PortInformation(data_type=str, required=True)}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "create_case_obj": "/create_case_obj",
            "create_case_addressees": "/create_case_addressees",
            "activity_id": "/activity_id",
        }

    def initialise(self) -> None:
        from py_trees.ports import NoDataAvailable

        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")
        try:
            self.create_case_obj_bb = self.get_input("create_case_obj")
        except NoDataAvailable:
            self.create_case_obj_bb = None
            self.feedback_message = (
                f"{self.name}: 'create_case_obj' not on blackboard"
            )
        try:
            self.create_case_addressees_bb: list = self.get_input(
                "create_case_addressees"
            )
        except NoDataAvailable:
            self.create_case_addressees_bb = []
            self.feedback_message = (
                f"{self.name}: 'create_case_addressees' not on blackboard"
            )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self.case_id_bb
        if not isinstance(case_id, str):
            self.logger.error(
                f"{self.name}: case_id must be a string, got {type(case_id)}"
            )
            return Status.FAILURE

        case_obj = self.create_case_obj_bb
        if case_obj is None:
            self.feedback_message = (
                f"{self.name}: 'create_case_obj' not on blackboard"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        addressees = self.create_case_addressees_bb
        if not isinstance(addressees, list):
            self.logger.error(
                f"{self.name}: create_case_addressees must be a list"
            )
            return Status.FAILURE

        activity = VultronCreateCaseActivity(
            actor=self.actor_id,
            object_=case_obj,
            context=case_id,
            to=addressees if addressees else None,
        )
        try:
            self.datalayer.create(activity)
            self.logger.info(
                f"{self.name}: Created CreateCaseActivity activity"
                f" {activity.id_}"
            )
        except ValueError as e:
            self.logger.warning(
                f"{self.name}: CreateCaseActivity activity {activity.id_}"
                f" already exists: {e}"
            )

        self._set_output("activity_id", activity.id_)
        return Status.SUCCESS
