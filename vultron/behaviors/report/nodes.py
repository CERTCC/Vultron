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
Report validation behavior tree nodes.

This module provides condition and action nodes for the report validation
workflow, implementing the logic from the validate_report handler as a
composable behavior tree.

Per specs/behavior-tree-integration.md BT-07 and BT-10 requirements.
"""

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.api.v2.data.status import (
    OfferStatus,
    ReportStatus,
    get_status_layer,
    set_status,
)
from vultron.api.v2.datalayer.db_record import object_to_record
from vultron.as_vocab.activities.case import CreateCase as as_CreateCase
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.bt.report_management.states import RM
from vultron.enums import OfferStatusEnum

logger = logging.getLogger(__name__)


# ============================================================================
# Condition Nodes
# ============================================================================


class CheckRMStateValid(DataLayerCondition):
    """
    Check if report is already in RM.VALID state.

    Returns SUCCESS if report status is RM.VALID (early exit optimization).
    Returns FAILURE if report is in any other state.

    This node implements the early-exit check from the simulation BT.
    """

    def __init__(self, report_id: str, name: str | None = None):
        """
        Initialize CheckRMStateValid node.

        Args:
            report_id: ID of VulnerabilityReport to check
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        """
        Check if report is in RM.VALID state.

        Returns:
            SUCCESS if report is RM.VALID, FAILURE otherwise
        """
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            # Get status from status layer
            status_layer = get_status_layer()
            report_status_dict = status_layer.get(
                "VulnerabilityReport", {}
            ).get(self.report_id, {})

            # Check if any actor has this report in VALID state
            for actor_id, status_data in report_status_dict.items():
                if status_data.get("status") == RM.VALID:
                    self.logger.debug(
                        f"{self.name}: Report {self.report_id} already VALID for actor {actor_id}"
                    )
                    return Status.SUCCESS

            self.logger.debug(
                f"{self.name}: Report {self.report_id} not in VALID state"
            )
            return Status.FAILURE

        except Exception as e:
            self.logger.error(f"{self.name}: Error checking report state: {e}")
            return Status.FAILURE


class CheckRMStateReceivedOrInvalid(DataLayerCondition):
    """
    Check if report is in RM.RECEIVED or RM.INVALID state.

    Returns SUCCESS if report is in acceptable precondition state.
    Returns FAILURE if report is in any other state (e.g., CLOSED, VALID).

    This node implements the precondition check from the simulation BT.
    """

    def __init__(self, report_id: str, name: str | None = None):
        """
        Initialize CheckRMStateReceivedOrInvalid node.

        Args:
            report_id: ID of VulnerabilityReport to check
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        """
        Check if report is in RM.RECEIVED or RM.INVALID state.

        Returns:
            SUCCESS if report is in acceptable state, FAILURE otherwise
        """
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            status_layer = get_status_layer()
            report_status_dict = status_layer.get(
                "VulnerabilityReport", {}
            ).get(self.report_id, {})

            # If no status found, assume RECEIVED (default)
            if not report_status_dict:
                self.logger.debug(
                    f"{self.name}: No status found for report {self.report_id}, assuming RECEIVED"
                )
                return Status.SUCCESS

            # Check if any actor has this report in RECEIVED or INVALID state
            for actor_id, status_data in report_status_dict.items():
                status = status_data.get("status")
                if status in (RM.RECEIVED, RM.INVALID):
                    self.logger.debug(
                        f"{self.name}: Report {self.report_id} in acceptable state ({status}) for actor {actor_id}"
                    )
                    return Status.SUCCESS

            self.logger.debug(
                f"{self.name}: Report {self.report_id} not in RECEIVED or INVALID state"
            )
            return Status.FAILURE

        except Exception as e:
            self.logger.error(f"{self.name}: Error checking report state: {e}")
            return Status.FAILURE


# ============================================================================
# Action Nodes
# ============================================================================


class TransitionRMtoValid(DataLayerAction):
    """
    Transition report to RM.VALID and offer to ACCEPTED.

    Updates both report status (RM.VALID) and offer status (ACCEPTED) in the
    status layer. Logs state transitions at INFO level.

    This node implements the core state transition from the validate_report handler.
    """

    def __init__(self, report_id: str, offer_id: str, name: str | None = None):
        """
        Initialize TransitionRMtoValid node.

        Args:
            report_id: ID of VulnerabilityReport to update
            offer_id: ID of Offer to update
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.offer_id = offer_id

    def update(self) -> Status:
        """
        Update report and offer statuses.

        Returns:
            SUCCESS if both statuses updated, FAILURE on error
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            # Update offer status to ACCEPTED
            offer_status = OfferStatus(
                object_type="Offer",
                object_id=self.offer_id,
                status=OfferStatusEnum.ACCEPTED,
                actor_id=self.actor_id,
            )
            set_status(offer_status)
            self.logger.info(
                f"{self.name}: Set offer {self.offer_id} to ACCEPTED"
            )

            # Update report status to VALID
            report_status = ReportStatus(
                object_type="VulnerabilityReport",
                object_id=self.report_id,
                status=RM.VALID,
                actor_id=self.actor_id,
            )
            set_status(report_status)
            self.logger.info(
                f"{self.name}: Set report {self.report_id} to VALID"
            )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error transitioning to VALID: {e}"
            )
            return Status.FAILURE


class TransitionRMtoInvalid(DataLayerAction):
    """
    Transition report to RM.INVALID and offer to TENTATIVELY_REJECTED.

    Updates both report status (RM.INVALID) and offer status (TENTATIVELY_REJECTED)
    in the status layer. Logs state transitions at INFO level.

    This node implements the invalidation path for future fallback sequences.
    """

    def __init__(self, report_id: str, offer_id: str, name: str | None = None):
        """
        Initialize TransitionRMtoInvalid node.

        Args:
            report_id: ID of VulnerabilityReport to update
            offer_id: ID of Offer to update
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.offer_id = offer_id

    def update(self) -> Status:
        """
        Update report and offer statuses.

        Returns:
            SUCCESS if both statuses updated, FAILURE on error
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            # Update offer status to TENTATIVELY_REJECTED
            offer_status = OfferStatus(
                object_type="Offer",
                object_id=self.offer_id,
                status=OfferStatusEnum.TENTATIVELY_REJECTED,
                actor_id=self.actor_id,
            )
            set_status(offer_status)
            self.logger.info(
                f"{self.name}: Set offer {self.offer_id} to TENTATIVELY_REJECTED"
            )

            # Update report status to INVALID
            report_status = ReportStatus(
                object_type="VulnerabilityReport",
                object_id=self.report_id,
                status=RM.INVALID,
                actor_id=self.actor_id,
            )
            set_status(report_status)
            self.logger.info(
                f"{self.name}: Set report {self.report_id} to INVALID"
            )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error transitioning to INVALID: {e}"
            )
            return Status.FAILURE


class CreateCaseNode(DataLayerAction):
    """
    Create VulnerabilityCase from validated report.

    Creates a new VulnerabilityCase containing the validated report and persists
    it to the DataLayer. Stores the case ID in the blackboard for subsequent nodes.

    This node implements case creation from the validate_report handler.

    Note: Named CreateCaseNode (not CreateCase) to avoid conflict with
    as_CreateCase activity class.
    """

    def __init__(self, report_id: str, name: str | None = None):
        """
        Initialize CreateCaseNode.

        Args:
            report_id: ID of VulnerabilityReport to include in case
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        """
        Create VulnerabilityCase and persist to DataLayer.

        Returns:
            SUCCESS if case created, FAILURE on error
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            # Read report object to get report reference
            report_obj = self.datalayer.read(
                self.report_id, raise_on_missing=True
            )

            # Create VulnerabilityCase
            case = VulnerabilityCase(
                name=f"Case for Report {self.report_id}",
                vulnerability_reports=[report_obj],
                attributed_to=self.actor_id,
            )

            # Store case in DataLayer
            try:
                self.datalayer.create(case)
                self.logger.info(
                    f"{self.name}: Created VulnerabilityCase {case.as_id}: {case.name}"
                )
            except ValueError as e:
                # Case already exists (idempotency)
                self.logger.warning(
                    f"{self.name}: VulnerabilityCase {case.as_id} already exists: {e}"
                )

            # Store case_id in blackboard for CreateCaseActivity node
            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.case_id = case.as_id

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error creating case: {e}")
            return Status.FAILURE


class CreateCaseActivity(DataLayerAction):
    """
    Create CreateCase activity for case creation notification.

    Generates a CreateCase activity to notify relevant actors about the new case.
    Collects addressees from actor, report.attributed_to, and offer.to fields.

    This node implements activity generation from the validate_report handler.
    """

    def __init__(self, report_id: str, offer_id: str, name: str | None = None):
        """
        Initialize CreateCaseActivity node.

        Args:
            report_id: ID of VulnerabilityReport (for addressee collection)
            offer_id: ID of Offer (for addressee collection)
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.offer_id = offer_id

    def update(self) -> Status:
        """
        Create CreateCase activity and persist to DataLayer.

        Returns:
            SUCCESS if activity created, FAILURE on error
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            # Get case_id from blackboard (set by CreateCaseNode)
            case_id = self.blackboard.get("case_id")
            if case_id is None:
                self.logger.error(
                    f"{self.name}: case_id not found in blackboard"
                )
                return Status.FAILURE

            # Read objects for addressee collection
            actor = self.datalayer.read(self.actor_id, raise_on_missing=True)
            report = self.datalayer.read(self.report_id, raise_on_missing=True)
            offer = self.datalayer.read(self.offer_id, raise_on_missing=True)

            # Collect addressees (same logic as handler)
            addressees = []
            for x in [actor, report.attributed_to, offer.to]:
                if x is None:
                    continue
                if isinstance(x, str):
                    addressees.append(x)
                elif isinstance(x, list):
                    for item in x:
                        if isinstance(item, str):
                            addressees.append(item)
                        elif hasattr(item, "as_id"):
                            addressees.append(item.as_id)
                elif hasattr(x, "as_id"):
                    addressees.append(x.as_id)

            # Unique addressees
            addressees = list(set(addressees))
            self.logger.info(
                f"{self.name}: Notifying addressees: {addressees}"
            )

            # Create CreateCase activity
            create_case_activity = as_CreateCase(
                actor=self.actor_id, object=case_id, to=addressees
            )

            # Store activity in DataLayer
            try:
                self.datalayer.create(create_case_activity)
                self.logger.info(
                    f"{self.name}: Created CreateCase activity: {create_case_activity.as_id}"
                )
            except ValueError as e:
                self.logger.warning(
                    f"{self.name}: CreateCase activity {create_case_activity.as_id} already exists: {e}"
                )

            # Store activity_id in blackboard for UpdateActorOutbox node
            self.blackboard.register_key(
                key="activity_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.activity_id = create_case_activity.as_id

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error creating CreateCase activity: {e}"
            )
            return Status.FAILURE


class UpdateActorOutbox(DataLayerAction):
    """
    Update actor's outbox with new activity.

    Appends the CreateCase activity ID to the actor's outbox.items list and
    persists the updated actor to the DataLayer.

    This node implements the outbox update from the validate_report handler.
    """

    def __init__(self, name: str | None = None):
        """
        Initialize UpdateActorOutbox node.

        Args:
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)

    def update(self) -> Status:
        """
        Update actor's outbox with activity ID.

        Returns:
            SUCCESS if outbox updated, FAILURE on error
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            # Get activity_id from blackboard (set by CreateCaseActivity)
            activity_id = self.blackboard.get("activity_id")
            if activity_id is None:
                self.logger.error(
                    f"{self.name}: activity_id not found in blackboard"
                )
                return Status.FAILURE

            # Read actor
            actor_obj = self.datalayer.read(
                self.actor_id, raise_on_missing=True
            )

            # Verify actor has outbox
            if not hasattr(actor_obj, "outbox") or not hasattr(
                actor_obj.outbox, "items"
            ):
                self.logger.error(
                    f"{self.name}: Actor {self.actor_id} has no outbox or outbox.items"
                )
                return Status.FAILURE

            # Append activity to outbox
            actor_obj.outbox.items.append(activity_id)
            self.logger.info(
                f"{self.name}: Added activity {activity_id} to actor {self.actor_id} outbox"
            )

            # Persist updated actor
            self.datalayer.update(actor_obj.as_id, object_to_record(actor_obj))
            self.logger.info(
                f"{self.name}: Updated actor {self.actor_id} in DataLayer"
            )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error updating actor outbox: {e}")
            return Status.FAILURE


# ============================================================================
# Policy Nodes (Stubs for Phase 1)
# ============================================================================


class EvaluateReportCredibility(DataLayerCondition):
    """
    Evaluate report credibility using policy.

    Phase 1: Always returns SUCCESS (stub implementation).
    Future: Implement configurable policy for credibility checks.

    This node implements the credibility check from the simulation BT.
    """

    def __init__(self, report_id: str, name: str | None = None):
        """
        Initialize EvaluateReportCredibility node.

        Args:
            report_id: ID of VulnerabilityReport to evaluate
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        """
        Evaluate report credibility (stub: always succeeds).

        Returns:
            SUCCESS (always, for Phase 1)
        """
        self.logger.info(
            f"{self.name}: Evaluating credibility for report {self.report_id} (stub: always accepts)"
        )
        return Status.SUCCESS


class EvaluateReportValidity(DataLayerCondition):
    """
    Evaluate report technical validity using policy.

    Phase 1: Always returns SUCCESS (stub implementation).
    Future: Implement configurable policy for validity checks.

    This node implements the validity check from the simulation BT.
    """

    def __init__(self, report_id: str, name: str | None = None):
        """
        Initialize EvaluateReportValidity node.

        Args:
            report_id: ID of VulnerabilityReport to evaluate
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        """
        Evaluate report validity (stub: always succeeds).

        Returns:
            SUCCESS (always, for Phase 1)
        """
        self.logger.info(
            f"{self.name}: Evaluating validity for report {self.report_id} (stub: always accepts)"
        )
        return Status.SUCCESS
