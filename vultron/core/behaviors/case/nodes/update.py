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

"""Action and condition nodes for case update behavior trees."""

from __future__ import annotations

from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.update_support import (
    apply_update_case_fields,
    broadcast_case_update,
    find_excluded_actor_ids,
)
from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerCondition,
)
from vultron.core.models.events.case import UpdateCaseReceivedEvent
from vultron.core.models.protocols import is_case_model
from vultron.core.use_cases._helpers import _as_id


class CheckCaseUpdateOwnerNode(DataLayerCondition):
    """Return SUCCESS when the current actor owns the case."""

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"case '{self.case_id}' not found"
            self.logger.warning(
                "%s: case '%s' not found in DataLayer",
                self.name,
                self.case_id,
            )
            return Status.FAILURE

        owner_id = _as_id(case.attributed_to)
        if owner_id != self.actor_id:
            self.feedback_message = f"actor '{self.actor_id}' is not the owner of case '{self.case_id}'"
            self.logger.info(
                "%s: actor '%s' is not the owner of case '%s' (owner: '%s')"
                " — skipping update-case handling",
                self.name,
                self.actor_id,
                self.case_id,
                owner_id,
            )
            return Status.FAILURE
        return Status.SUCCESS


class CaptureCaseUpdateBroadcastExclusionsNode(DataLayerCondition):
    """Resolve embargo-based broadcast exclusions for the case update."""

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="excluded_actor_ids", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"case '{self.case_id}' not found"
            self.logger.warning(
                "%s: case '%s' not found in DataLayer",
                self.name,
                self.case_id,
            )
            return Status.FAILURE

        self.blackboard.excluded_actor_ids = find_excluded_actor_ids(
            case, self.datalayer
        )
        return Status.SUCCESS


class ApplyCaseUpdateNode(DataLayerAction):
    """Apply mutable fields from the inbound update payload to the case."""

    def __init__(
        self,
        case_id: str,
        request: UpdateCaseReceivedEvent,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.request = request

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        stored_case = self.datalayer.read(self.case_id)
        if not is_case_model(stored_case):
            self.logger.warning(
                "%s: case '%s' not found in DataLayer",
                self.name,
                self.case_id,
            )
            return Status.FAILURE

        if apply_update_case_fields(stored_case, self.request):
            self.datalayer.save(stored_case)
            self.logger.info(
                "%s: Actor '%s' updated case '%s'",
                self.name,
                self.actor_id,
                self.case_id,
            )
        else:
            self.logger.info(
                "%s: object for case '%s' is a reference only — no fields to apply",
                self.name,
                self.case_id,
            )
        return Status.SUCCESS


class BroadcastCaseUpdateNode(DataLayerAction):
    """Broadcast the updated case to eligible participants."""

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="excluded_actor_ids", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"case '{self.case_id}' not found"
            self.logger.warning(
                "%s: case '%s' not found in DataLayer",
                self.name,
                self.case_id,
            )
            return Status.FAILURE

        try:
            excluded_actor_ids = self.blackboard.get("excluded_actor_ids")
        except KeyError:
            self.feedback_message = (
                "excluded_actor_ids not found in blackboard"
            )
            self.logger.error(
                "%s: excluded_actor_ids not found in blackboard", self.name
            )
            return Status.FAILURE

        if not isinstance(excluded_actor_ids, set):
            self.feedback_message = "excluded_actor_ids is not a set"
            self.logger.error("%s: excluded_actor_ids is not a set", self.name)
            return Status.FAILURE

        broadcast_case_update(
            self.datalayer,
            self.case_id,
            case,
            excluded_actor_ids=excluded_actor_ids,
        )
        return Status.SUCCESS
