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

Provides action nodes that emit outbound activities related to case creation
and case-manager role offers.
"""

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.protocols import is_case_model
from vultron.core.models.vultron_types import VultronCreateCaseActivity

logger = logging.getLogger(__name__)


class EmitCreateCaseActivity(DataLayerAction):
    """
    Generate a CreateCaseActivity activity and persist it to the DataLayer.

    Reads case_id from the blackboard (set by PersistCase), creates a
    CreateCaseActivity activity, and stores the activity_id in the blackboard for
    UpdateActorOutbox.
    """

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            case_id = self.blackboard.get("case_id")
            if case_id is None:
                self.logger.error(
                    f"{self.name}: case_id not found in blackboard"
                )
                return Status.FAILURE

            # Read full case to embed as object_ and derive addressees from
            # actor_participant_index, mirroring CreateCaseActivity in
            # report/nodes.py (D5-6-CASEPROP).
            case_obj = self.datalayer.read(case_id)
            if is_case_model(case_obj):
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

            activity = VultronCreateCaseActivity(
                actor=self.actor_id,
                object_=case_obj if case_obj is not None else case_id,
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

            self.blackboard.register_key(
                key="activity_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.activity_id = activity.id_

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error creating CreateCaseActivity activity: {e}"
            )
            return Status.FAILURE


class SendOfferCaseManagerRoleNode(DataLayerAction):
    """Send an Offer(VulnerabilityCase, target=CaseParticipant) to the Case Actor.

    Reads ``case_id`` and ``case_actor_id`` from the blackboard (written by
    ``CreateCaseNode`` and ``CreateCaseActorNode`` respectively), builds the
    deterministic participant ID, then calls
    ``trigger_activity_factory.offer_case_manager_role`` to create and persist
    the Offer activity.  Writes ``activity_id`` to the blackboard so that the
    following ``UpdateActorOutbox`` node can flush it to the actor's outbox.

    Per DEMOMA-08-002, DEMOMA-08-003; Issue #469.
    """

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        """Register blackboard keys: read case_id + case_actor_id, write activity_id."""
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_participant_id",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="activity_id", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        if self.trigger_activity_factory is None:
            self.logger.error(
                f"{self.name}: trigger_activity_factory not available"
            )
            return Status.FAILURE

        case_id = self.blackboard.get("case_id")
        case_actor_id = self.blackboard.get("case_actor_id")
        participant_id = self.blackboard.get("case_actor_participant_id")

        if not case_id or not case_actor_id or not participant_id:
            self.logger.error(
                f"{self.name}: case_id, case_actor_id, or"
                " case_actor_participant_id missing from blackboard"
            )
            return Status.FAILURE

        try:
            activity_id = (
                self.trigger_activity_factory.offer_case_manager_role(
                    case_id=case_id,
                    participant_id=participant_id,
                    actor=self.actor_id,
                    to=[case_actor_id],
                )
            )
            self.blackboard.activity_id = activity_id
            self.logger.info(
                "%s: Queued Offer(CaseManagerRole) '%s' to Case Actor '%s'"
                " for case '%s'",
                self.name,
                activity_id,
                case_actor_id,
                case_id,
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error sending Offer(CaseManagerRole): {e}"
            )
            return Status.FAILURE
