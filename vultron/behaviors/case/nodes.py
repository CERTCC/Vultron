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
Case management behavior tree nodes.

Provides condition and action nodes for the create_case workflow,
implementing idempotency guards, persistence, and outbox management
for VulnerabilityCase creation.

Per specs/behavior-tree-integration.md BT-07 and specs/case-management.md
CM-02 requirements.
"""

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.api.v2.datalayer.db_record import object_to_record
from vultron.as_vocab.activities.case import CreateCase as as_CreateCase
from vultron.as_vocab.objects.case_actor import CaseActor
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.behaviors.helpers import DataLayerAction, DataLayerCondition

logger = logging.getLogger(__name__)


# ============================================================================
# Condition Nodes
# ============================================================================


class CheckCaseAlreadyExists(DataLayerCondition):
    """
    Check if a VulnerabilityCase already exists in DataLayer.

    Returns SUCCESS if the case already exists (idempotency early exit).
    Returns FAILURE if the case does not exist (proceed with creation).

    Per specs/idempotency.md ID-04-004.
    """

    def __init__(self, case_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            existing = self.datalayer.read(self.case_id)
            if existing is not None:
                self.logger.info(
                    f"{self.name}: Case {self.case_id} already exists"
                    " — skipping creation (idempotent)"
                )
                return Status.SUCCESS

            self.logger.debug(
                f"{self.name}: Case {self.case_id} not found, proceeding"
            )
            return Status.FAILURE

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error checking case existence: {e}"
            )
            return Status.FAILURE


class ValidateCaseObject(DataLayerCondition):
    """
    Validate the incoming VulnerabilityCase object has required fields.

    Returns SUCCESS if the case object passes validation.
    Returns FAILURE if required fields are missing.
    """

    def __init__(self, case_obj: VulnerabilityCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def update(self) -> Status:
        try:
            if self.case_obj is None:
                self.logger.error(f"{self.name}: case_obj is None")
                return Status.FAILURE

            if not getattr(self.case_obj, "as_id", None):
                self.logger.error(f"{self.name}: Case object missing as_id")
                return Status.FAILURE

            self.logger.debug(
                f"{self.name}: Case {self.case_obj.as_id} passes validation"
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error validating case: {e}")
            return Status.FAILURE


# ============================================================================
# Action Nodes
# ============================================================================


class PersistCase(DataLayerAction):
    """
    Persist a VulnerabilityCase to the DataLayer.

    Creates the case record in DataLayer and stores the case_id in the
    blackboard for subsequent nodes.

    Per specs/case-management.md CM-02-001.
    """

    def __init__(self, case_obj: VulnerabilityCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            self.datalayer.create(self.case_obj)
            self.logger.info(
                f"{self.name}: Persisted VulnerabilityCase"
                f" {self.case_obj.as_id}"
            )

            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.case_id = self.case_obj.as_id

            return Status.SUCCESS

        except ValueError as e:
            self.logger.warning(
                f"{self.name}: Case {self.case_obj.as_id} already exists: {e}"
            )
            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.case_id = self.case_obj.as_id
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error persisting case: {e}")
            return Status.FAILURE


class CreateCaseActorNode(DataLayerAction):
    """
    Create a CaseActor (Service) for the new VulnerabilityCase.

    Each VulnerabilityCase MUST have exactly one associated CaseActor.
    The CaseActor is an ActivityStreams Service that manages case
    communications (inbox/outbox).

    Per specs/case-management.md CM-02-001.
    """

    def __init__(self, case_id: str, actor_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.actor_id = actor_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            case_actor = CaseActor(
                name=f"CaseActor for {self.case_id}",
                attributed_to=self.actor_id,
                context=self.case_id,
            )
            try:
                self.datalayer.create(case_actor)
                self.logger.info(
                    f"{self.name}: Created CaseActor {case_actor.as_id}"
                    f" for case {self.case_id}"
                )
            except ValueError as e:
                self.logger.warning(
                    f"{self.name}: CaseActor {case_actor.as_id}"
                    f" already exists: {e}"
                )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error creating CaseActor: {e}")
            return Status.FAILURE


class EmitCreateCaseActivity(DataLayerAction):
    """
    Generate a CreateCase activity and persist it to the DataLayer.

    Reads case_id from the blackboard (set by PersistCase), creates a
    CreateCase activity, and stores the activity_id in the blackboard for
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

            activity = as_CreateCase(
                actor=self.actor_id,
                object=case_id,
            )
            try:
                self.datalayer.create(activity)
                self.logger.info(
                    f"{self.name}: Created CreateCase activity"
                    f" {activity.as_id}"
                )
            except ValueError as e:
                self.logger.warning(
                    f"{self.name}: CreateCase activity {activity.as_id}"
                    f" already exists: {e}"
                )

            self.blackboard.register_key(
                key="activity_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.activity_id = activity.as_id

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error creating CreateCase activity: {e}"
            )
            return Status.FAILURE


class UpdateActorOutbox(DataLayerAction):
    """
    Append the CreateCase activity to the actor's outbox.

    Reads activity_id from blackboard (set by EmitCreateCaseActivity) and
    appends it to the actor's outbox.items list.
    """

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
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

            actor_obj = self.datalayer.read(
                self.actor_id, raise_on_missing=True
            )

            if not hasattr(actor_obj, "outbox") or not hasattr(
                actor_obj.outbox, "items"
            ):
                self.logger.error(
                    f"{self.name}: Actor {self.actor_id} has no outbox"
                )
                return Status.FAILURE

            actor_obj.outbox.items.append(activity_id)
            self.datalayer.update(actor_obj.as_id, object_to_record(actor_obj))
            self.logger.info(
                f"{self.name}: Added activity {activity_id} to"
                f" actor {self.actor_id} outbox"
            )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error updating actor outbox: {e}")
            return Status.FAILURE
