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

Delegation-related nodes (``ResolveCaseManagerOfferContextNode``,
``CreateOfferCaseManagerActivityNode``, ``AutoAcceptCaseManagerRoleNode``,
``EmitRejectCaseManagerRoleNode``) live in the sibling ``delegation.py``
module.
"""

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.vultron_types import VultronCreateCaseActivity

logger = logging.getLogger(__name__)


class CollectCaseAddresseesNode(DataLayerAction):
    """Resolve case object and peer addressees for Create(Case) emission."""

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="create_case_obj", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="create_case_addressees", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            case_id = self.blackboard.get("case_id")
        except KeyError:
            self.logger.error(f"{self.name}: case_id not found in blackboard")
            return Status.FAILURE
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

        self.blackboard.create_case_obj = case_obj
        self.blackboard.create_case_addressees = addressees
        return Status.SUCCESS


class CreateAndPersistCaseActivityNode(DataLayerAction):
    """Build and persist Create(Case), then publish activity_id to blackboard."""

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="create_case_obj", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="create_case_addressees", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="activity_id", access=py_trees.common.Access.WRITE
        )

    def _read_case_id(self) -> str | None:
        try:
            case_id = self.blackboard.get("case_id")
        except KeyError:
            self.logger.error(f"{self.name}: case_id not found in blackboard")
            return None
        if not isinstance(case_id, str):
            self.logger.error(
                f"{self.name}: case_id must be a string, got {type(case_id)}"
            )
            return None
        return case_id

    def _read_case_obj(self) -> Any | None:
        try:
            return self.blackboard.get("create_case_obj")
        except KeyError:
            self.feedback_message = (
                f"{self.name}: 'create_case_obj' not on blackboard"
            )
            self.logger.error(self.feedback_message)
            return None

    def _read_addressees(self) -> list[str] | None:
        try:
            addressees = self.blackboard.get("create_case_addressees")
        except KeyError:
            return []
        if not isinstance(addressees, list):
            self.logger.error(
                f"{self.name}: create_case_addressees must be a list"
            )
            return None
        return addressees

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        case_id = self._read_case_id()
        if case_id is None:
            return Status.FAILURE

        case_obj = self._read_case_obj()
        if case_obj is None:
            return Status.FAILURE

        addressees = self._read_addressees()
        if addressees is None:
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

        self.blackboard.activity_id = activity.id_
        return Status.SUCCESS
