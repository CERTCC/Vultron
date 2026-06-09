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

"""Outbound emit nodes for the report behavior tree."""

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases._helpers import case_addressees


class EmitEngageCaseActivity(DataLayerAction):
    """Emit RmEngageCaseActivity (Join(VulnerabilityCase)) to the actor outbox.

    Creates the activity, persists it to the datalayer (idempotent), appends
    its ID to the actor's ``outbox.items`` collection, and queues it for
    delivery via ``record_outbox_item``.

    Phase 1: Always called after EvaluateCasePriority returns SUCCESS.
    Future: May be gated by an SSVC policy node (IDEA-26041004).

    Per specs/behavior-tree-integration.yaml BT-06-005.
    """

    def __init__(self, case_id: str, actor_id: str, name: str | None = None):
        """
        Initialize EmitEngageCaseActivity node.

        Args:
            case_id: ID of VulnerabilityCase the actor is engaging
            actor_id: ID of Actor emitting the engage activity
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.actor_id = actor_id

    def update(self) -> Status:
        """
        Create and queue RmEngageCaseActivity.

        Returns:
            SUCCESS if activity created and outbox updated, FAILURE on error
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        if self.trigger_activity_factory is None:
            self.logger.warning(
                "%s: no TriggerActivityPort — cannot emit EngageCase activity",
                self.name,
            )
            return Status.FAILURE

        try:
            case = self.datalayer.read(self.case_id)
            addressees: list[str] | None = None
            if is_case_model(case):
                recipients = case_addressees(case, self.actor_id)
                if recipients:
                    addressees = recipients

            activity_id, _ = self.trigger_activity_factory.engage_case(
                case_id=self.case_id,
                actor=self.actor_id,
                to=addressees,
            )

            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            self.logger.info(
                "Actor '%s' emitted RmEngageCaseActivity for case '%s'",
                self.actor_id,
                self.case_id,
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error emitting engage activity: {e}"
            )
            return Status.FAILURE


class EmitDeferCaseActivity(DataLayerAction):
    """Emit RmDeferCaseActivity (Ignore(VulnerabilityCase)) to the actor outbox.

    Creates the activity, persists it to the datalayer (idempotent), appends
    its ID to the actor's ``outbox.items`` collection, and queues it for
    delivery via ``record_outbox_item``.

    Called when EvaluateCasePriority returns FAILURE (defer path in
    PrioritizeBT).

    Per specs/behavior-tree-integration.yaml BT-06-006.
    """

    def __init__(self, case_id: str, actor_id: str, name: str | None = None):
        """
        Initialize EmitDeferCaseActivity node.

        Args:
            case_id: ID of VulnerabilityCase the actor is deferring
            actor_id: ID of Actor emitting the defer activity
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.actor_id = actor_id

    def update(self) -> Status:
        """
        Create and queue RmDeferCaseActivity.

        Returns:
            SUCCESS if activity created and outbox updated, FAILURE on error
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        if self.trigger_activity_factory is None:
            self.logger.warning(
                "%s: no TriggerActivityPort — cannot emit DeferCase activity",
                self.name,
            )
            return Status.FAILURE

        try:
            case = self.datalayer.read(self.case_id)
            addressees: list[str] | None = None
            if is_case_model(case):
                recipients = case_addressees(case, self.actor_id)
                if recipients:
                    addressees = recipients

            activity_id, _ = self.trigger_activity_factory.defer_case(
                case_id=self.case_id,
                actor=self.actor_id,
                to=addressees,
            )

            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            self.logger.info(
                "Actor '%s' emitted RmDeferCaseActivity for case '%s'",
                self.actor_id,
                self.case_id,
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error emitting defer activity: {e}"
            )
            return Status.FAILURE
