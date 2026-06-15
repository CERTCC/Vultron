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

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.protocols import is_case_model
from vultron.core.use_cases._helpers import _resolve_case_manager_id
from vultron.core.use_cases.triggers._helpers import add_activity_to_outbox


class ResolveCaseManagerNode(DataLayerAction):
    """Look up the CASE_MANAGER actor ID and write it to the blackboard."""

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_manager_id",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = (
                f"Case '{self.case_id}' not found or wrong type"
            )
            return Status.FAILURE

        case_manager_id = _resolve_case_manager_id(case, self.datalayer)
        if case_manager_id is None:
            self.feedback_message = (
                f"No CASE_MANAGER participant found in case '{self.case_id}'"
            )
            return Status.FAILURE

        self.blackboard.case_manager_id = case_manager_id
        self.logger.debug(
            "Resolved CASE_MANAGER actor for case '%s'", self.case_id
        )
        return Status.SUCCESS


class ConstructActivitiesNode(DataLayerAction):
    """Build outbound AS2 activities and write their IDs to the blackboard."""

    def __init__(
        self,
        activity_builder: Callable[[str], list[str]],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._activity_builder = activity_builder

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_manager_id",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="activity_ids",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        try:
            case_manager_id: str = self.blackboard.case_manager_id
        except KeyError:
            self.feedback_message = "case_manager_id not in blackboard"
            return Status.FAILURE

        try:
            activity_ids = self._activity_builder(case_manager_id)
        except Exception as exc:
            self.feedback_message = f"Activity construction failed: {exc}"
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        self.blackboard.activity_ids = activity_ids
        self.logger.debug(
            "Constructed %d outbound activity/activities", len(activity_ids)
        )
        return Status.SUCCESS


class QueueToOutboxNode(DataLayerAction):
    """Queue each activity ID from the blackboard to the actor's outbox."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity_ids",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        try:
            activity_ids: list[str] = self.blackboard.activity_ids
        except KeyError:
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
