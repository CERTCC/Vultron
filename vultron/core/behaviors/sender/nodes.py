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
BT nodes for the sender-side routing pattern.

Provides the three nodes that compose the SenderSideBT sequence:

    SenderSideBT (Sequence)
    ├─ ResolveCaseManagerNode    # look up CASE_MANAGER actor ID
    ├─ ConstructActivitiesNode   # build outbound AS2 activities
    └─ QueueToOutboxNode         # append activity IDs to actor outbox

Per specs/participant-case-replica.yaml PCR-08-001, PCR-08-002.
"""

from typing import Callable

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.protocols import is_case_model
from vultron.core.use_cases._helpers import _resolve_case_manager_id
from vultron.core.use_cases.triggers._helpers import add_activity_to_outbox


class ResolveCaseManagerNode(DataLayerAction):
    """Look up the CASE_MANAGER actor ID and write it to the blackboard.

    Reads the VulnerabilityCase from the DataLayer, iterates over its
    participants, and finds the one holding ``CVDRole.CASE_MANAGER``.
    Writes that participant's ``attributed_to`` actor ID to the blackboard
    under the key ``case_manager_id``.

    Returns SUCCESS when a Case Manager is found.
    Returns FAILURE when the case does not exist or no CASE_MANAGER
    participant is found (the parent Sequence will halt and the use case
    will raise a domain error).

    Per PCR-08-001: all participant-originated activities MUST be addressed
    to the Case Actor (the CASE_MANAGER participant's actor) exclusively.
    """

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
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
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
    """Build outbound AS2 activities and write their IDs to the blackboard.

    Reads ``case_manager_id`` from the blackboard (written by
    :class:`ResolveCaseManagerNode`) and passes it to *activity_builder*,
    a callable that constructs the AS2 activity (or activities) addressed
    to the Case Actor and returns the resulting activity IDs as a list.

    Writes the returned list to the blackboard under the key
    ``activity_ids`` for :class:`QueueToOutboxNode` to consume.

    *activity_builder* signature::

        (case_manager_id: str) -> list[str]

    It typically captures the trigger-activity factory and any additional
    use-case context (``actor_id``, payload IDs, etc.) via closure.

    Returns SUCCESS when the builder succeeds.
    Returns FAILURE on any exception raised by the builder.
    """

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
    """Queue each activity ID from the blackboard to the actor's outbox.

    Reads the ``activity_ids`` list written by
    :class:`ConstructActivitiesNode` and calls ``add_activity_to_outbox``
    for each, using the ``actor_id`` set on the blackboard by
    ``BTBridge.setup_tree()``.

    Returns SUCCESS after all activities have been queued.
    Returns FAILURE when the DataLayer or ``actor_id`` is unavailable, or
    when queueing any activity raises an exception.
    """

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
                # CaseOutboxPersistence is a superset of CasePersistence;
                # trigger use cases always pass a CaseOutboxPersistence
                # implementation, so this cast is safe.
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
