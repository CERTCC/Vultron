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

from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCreateCaseActivity,
    VultronParticipantStatus,
)
from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerCondition,
)
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import (
    _idempotent_create,
    _report_phase_status_id,
)
from vultron.core.use_cases.triggers._helpers import (
    update_participant_rm_state,
)

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

        valid_id = _report_phase_status_id(
            self.actor_id, self.report_id, RM.VALID.value
        )
        if self.datalayer.get("ParticipantStatus", valid_id) is not None:
            self.logger.debug(
                f"{self.name}: Report {self.report_id} already VALID"
            )
            return Status.SUCCESS
        self.logger.debug(
            f"{self.name}: Report {self.report_id} not in VALID state"
        )
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

        # Return FAILURE if already VALID (can't re-validate)
        valid_id = _report_phase_status_id(
            self.actor_id, self.report_id, RM.VALID.value
        )
        if self.datalayer.get("ParticipantStatus", valid_id) is not None:
            self.logger.debug(
                f"{self.name}: Report {self.report_id} already VALID - precondition failed"
            )
            return Status.FAILURE

        self.logger.debug(
            f"{self.name}: Report {self.report_id} in acceptable state for validation"
        )
        return Status.SUCCESS


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
            status = VultronParticipantStatus(
                as_id=_report_phase_status_id(
                    self.actor_id, self.report_id, RM.VALID.value
                ),
                context=self.report_id,
                attributed_to=self.actor_id,
                rm_state=RM.VALID,
            )
            _idempotent_create(
                self.datalayer,
                "ParticipantStatus",
                status.as_id,
                status,
                "ParticipantStatus (report-phase RM.VALID)",
            )
            self.logger.info(
                f"{self.name}: Set report {self.report_id} to VALID (actor {self.actor_id})"
            )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error transitioning to VALID: {e}"
            )
            return Status.FAILURE


class TransitionRMtoInvalid(DataLayerAction):
    """
    Transition report to RM.INVALID.

    Persists a ParticipantStatus record with RM.INVALID for the actor and
    report in the DataLayer.
    Logs state transitions at INFO level.

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
        Update report status to INVALID in DataLayer.

        Returns:
            SUCCESS if status updated, FAILURE on error
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            status = VultronParticipantStatus(
                as_id=_report_phase_status_id(
                    self.actor_id, self.report_id, RM.INVALID.value
                ),
                context=self.report_id,
                attributed_to=self.actor_id,
                rm_state=RM.INVALID,
            )
            _idempotent_create(
                self.datalayer,
                "ParticipantStatus",
                status.as_id,
                status,
                "ParticipantStatus (report-phase RM.INVALID)",
            )
            self.logger.info(
                f"{self.name}: Set report {self.report_id} to INVALID (actor {self.actor_id})"
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

    Note: Named CreateCaseNode (not CreateCaseActivity) to avoid conflict with
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

            # Create VulnerabilityCase domain object
            report_id_ref = (
                report_obj.as_id
                if hasattr(report_obj, "as_id")
                else self.report_id
            )
            case = VultronCase(
                name=f"Case for Report {self.report_id}",
                vulnerability_reports=[report_id_ref],
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
    Create CreateCaseActivity activity for case creation notification.

    Generates a CreateCaseActivity activity to notify relevant actors about the new case.
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

    def setup(self, **kwargs: Any) -> None:
        """Set up blackboard access including case_id key."""
        super().setup(**kwargs)
        # Register READ access to case_id (set by CreateCaseNode)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        """
        Create CreateCaseActivity activity and persist to DataLayer.

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

            # Create CreateCaseActivity activity domain object
            create_case_activity = VultronCreateCaseActivity(
                actor=self.actor_id, object=case_id
            )

            # Store activity in DataLayer
            try:
                self.datalayer.create(create_case_activity)
                self.logger.info(
                    f"{self.name}: Created CreateCaseActivity activity: {create_case_activity.as_id}"
                )
            except ValueError as e:
                self.logger.warning(
                    f"{self.name}: CreateCaseActivity activity {create_case_activity.as_id} already exists: {e}"
                )

            # Store activity_id in blackboard for UpdateActorOutbox node
            self.blackboard.register_key(
                key="activity_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.activity_id = create_case_activity.as_id

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error creating CreateCaseActivity activity: {e}"
            )
            return Status.FAILURE


class UpdateActorOutbox(DataLayerAction):
    """
    Update actor's outbox with new activity.

    Appends the CreateCaseActivity activity ID to the actor's outbox.items list and
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

    def setup(self, **kwargs: Any) -> None:
        """Set up blackboard access including activity_id key."""
        super().setup(**kwargs)
        # Register READ access to activity_id (set by CreateCaseActivity)
        self.blackboard.register_key(
            key="activity_id", access=py_trees.common.Access.READ
        )

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
            self.datalayer.save(actor_obj)
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


# ============================================================================
# Case Prioritization Nodes (BT-2.1)
# ============================================================================


class CheckParticipantExists(DataLayerCondition):
    """
    Check if actor has a CaseParticipant record in the specified case.

    Returns SUCCESS if the actor's CaseParticipant is found in
    case.case_participants. Returns FAILURE if the case is not found or
    the actor has no participant record.

    This is the precondition for engage_case and defer_case BTs: RM state
    for a case is tracked in CaseParticipant.participant_status, so a
    participant record must exist before transitioning RM state.
    """

    def __init__(self, case_id: str, actor_id: str, name: str | None = None):
        """
        Initialize CheckParticipantExists node.

        Args:
            case_id: ID of VulnerabilityCase to check
            actor_id: ID of Actor to find in case_participants
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.actor_id = actor_id

    def update(self) -> Status:
        """
        Check whether actor has a CaseParticipant in the case.

        Returns:
            SUCCESS if participant found, FAILURE otherwise
        """
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            case_obj = self.datalayer.read(
                self.case_id, raise_on_missing=False
            )
            if case_obj is None:
                self.logger.debug(
                    f"{self.name}: Case {self.case_id} not found"
                )
                return Status.FAILURE

            for participant_ref in case_obj.case_participants:
                if isinstance(participant_ref, str):
                    participant = self.datalayer.read(participant_ref)
                    if participant is None:
                        continue
                else:
                    participant = participant_ref
                actor_ref = participant.attributed_to
                p_actor_id = (
                    actor_ref
                    if isinstance(actor_ref, str)
                    else getattr(actor_ref, "as_id", str(actor_ref))
                )
                if p_actor_id == self.actor_id:
                    self.logger.debug(
                        f"{self.name}: Participant found for actor {self.actor_id} in case {self.case_id}"
                    )
                    return Status.SUCCESS

            self.logger.debug(
                f"{self.name}: No participant for actor {self.actor_id} in case {self.case_id}"
            )
            return Status.FAILURE

        except Exception as e:
            self.logger.error(f"{self.name}: Error checking participant: {e}")
            return Status.FAILURE


def _find_and_update_participant_rm(
    datalayer, case_id: str, actor_id: str, new_rm_state, logger
) -> Status:
    """Thin BT wrapper: delegate to ``update_participant_rm_state`` and convert
    the boolean result to a py_trees ``Status``.

    Returns SUCCESS on success (including idempotent no-op), FAILURE when the
    case or participant is not found or an error occurs.
    """
    try:
        result = update_participant_rm_state(
            case_id, actor_id, new_rm_state, datalayer
        )
        return Status.SUCCESS if result else Status.FAILURE
    except Exception as e:
        logger.error(f"Error updating participant RM state: {e}")
        return Status.FAILURE


class TransitionParticipantRMtoAccepted(DataLayerAction):
    """
    Transition actor's RM state to ACCEPTED in the specified case.

    Finds the actor's CaseParticipant in case.case_participants, appends a
    new ParticipantStatus with rm_state=RM.ACCEPTED, and persists the
    updated case to the DataLayer.

    Called when an actor engages a case (receives RmEngageCaseActivity /
    Join(VulnerabilityCase)).
    """

    def __init__(self, case_id: str, actor_id: str, name: str | None = None):
        """
        Initialize TransitionParticipantRMtoAccepted node.

        Args:
            case_id: ID of VulnerabilityCase
            actor_id: ID of Actor whose RM state transitions to ACCEPTED
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.actor_id = actor_id

    def update(self) -> Status:
        """
        Append ParticipantStatus(rm_state=ACCEPTED) to actor's CaseParticipant.

        Returns:
            SUCCESS if transition persisted, FAILURE on error
        """
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        from vultron.core.states.rm import RM

        return _find_and_update_participant_rm(
            self.datalayer,
            self.case_id,
            self.actor_id,
            RM.ACCEPTED,
            self.logger,
        )


class TransitionParticipantRMtoDeferred(DataLayerAction):
    """
    Transition actor's RM state to DEFERRED in the specified case.

    Finds the actor's CaseParticipant in case.case_participants, appends a
    new ParticipantStatus with rm_state=RM.DEFERRED, and persists the
    updated case to the DataLayer.

    Called when an actor defers a case (receives RmDeferCaseActivity /
    Ignore(VulnerabilityCase)).
    """

    def __init__(self, case_id: str, actor_id: str, name: str | None = None):
        """
        Initialize TransitionParticipantRMtoDeferred node.

        Args:
            case_id: ID of VulnerabilityCase
            actor_id: ID of Actor whose RM state transitions to DEFERRED
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.actor_id = actor_id

    def update(self) -> Status:
        """
        Append ParticipantStatus(rm_state=DEFERRED) to actor's CaseParticipant.

        Returns:
            SUCCESS if transition persisted, FAILURE on error
        """
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        from vultron.core.states.rm import RM

        return _find_and_update_participant_rm(
            self.datalayer,
            self.case_id,
            self.actor_id,
            RM.DEFERRED,
            self.logger,
        )


class EvaluateCasePriority(DataLayerCondition):
    """
    Evaluate whether to engage or defer a case using prioritization policy.

    Phase 1: Always returns SUCCESS (stub — always engage).
    Future: Plug in SSVC or other priority framework via PrioritizationPolicy.

    This node is used when the local actor is DECIDING whether to engage or
    defer (i.e., generating an outgoing RmEngageCaseActivity or RmDeferCaseActivity message),
    as opposed to the receive-side nodes above which record a decision already
    made by the sending actor.

    See specs/prototype-shortcuts.md PROTO-05-001 for SSVC deferral policy.
    """

    def __init__(self, case_id: str, name: str | None = None):
        """
        Initialize EvaluateCasePriority node.

        Args:
            case_id: ID of VulnerabilityCase to evaluate
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        """
        Evaluate case priority (stub: always engage).

        Returns:
            SUCCESS (always, for Phase 1)
        """
        self.logger.info(
            f"{self.name}: Evaluating priority for case {self.case_id} (stub: always engage)"
        )
        return Status.SUCCESS
