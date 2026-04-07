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
from vultron.core.models.protocols import (
    has_outbox,
    is_case_model,
    is_participant_model,
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
from vultron.core.use_cases._helpers import (
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
        if self.actor_id is None:
            self.logger.error(f"{self.name}: actor_id not available")
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
        if self.actor_id is None:
            self.logger.error(f"{self.name}: actor_id not available")
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
                id_=_report_phase_status_id(
                    self.actor_id, self.report_id, RM.VALID.value
                ),
                context=self.report_id,
                attributed_to=self.actor_id,
                rm_state=RM.VALID,
            )
            _idempotent_create(
                self.datalayer,
                "ParticipantStatus",
                status.id_,
                status,
                "ParticipantStatus (report-phase RM.VALID)",
            )
            self.logger.info(
                "RM → VALID for report '%s' (actor '%s')",
                self.report_id,
                self.actor_id,
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
                id_=_report_phase_status_id(
                    self.actor_id, self.report_id, RM.INVALID.value
                ),
                context=self.report_id,
                attributed_to=self.actor_id,
                rm_state=RM.INVALID,
            )
            _idempotent_create(
                self.datalayer,
                "ParticipantStatus",
                status.id_,
                status,
                "ParticipantStatus (report-phase RM.INVALID)",
            )
            self.logger.info(
                "RM → INVALID for report '%s' (actor '%s')",
                self.report_id,
                self.actor_id,
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
            if report_obj is None:
                self.logger.error(
                    f"{self.name}: Report {self.report_id} not found"
                )
                return Status.FAILURE

            # Create VulnerabilityCase domain object
            report_id_ref = report_obj.id_
            case = VultronCase(
                name=f"Case for Report {self.report_id}",
                vulnerability_reports=[report_id_ref],
                attributed_to=self.actor_id,
            )

            # Store case in DataLayer
            try:
                self.datalayer.create(case)
                self.logger.info(
                    f"{self.name}: Created VulnerabilityCase {case.id_}: {case.name}"
                )
            except ValueError as e:
                # Case already exists (idempotency)
                self.logger.warning(
                    f"{self.name}: VulnerabilityCase {case.id_} already exists: {e}"
                )

            # Store case_id in blackboard for CreateCaseActivity node
            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.case_id = case.id_

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

            # Read objects for addressee collection.
            # VultronOffer (type_ = "Offer") is not in the AS2 vocabulary so
            # dl.read() cannot reconstruct it; use by_type() for the raw dict.
            actor = self.datalayer.read(self.actor_id, raise_on_missing=True)
            report = self.datalayer.read(self.report_id, raise_on_missing=True)
            offer_records = self.datalayer.by_type("Offer")
            offer_data = offer_records.get(self.offer_id)

            # Collect addressees (same logic as handler)
            addressees = []
            report_attributed_to = (
                getattr(report, "attributed_to", None)
                if report is not None
                else None
            )
            offer_to = offer_data.get("to") if offer_data is not None else None
            # Also include the offer submitter (offer.actor) — the finder who
            # created the report and submitted the offer needs to receive the
            # case so they can participate as a case participant.
            offer_actor = (
                offer_data.get("actor") if offer_data is not None else None
            )
            for x in [actor, report_attributed_to, offer_to, offer_actor]:
                if x is None:
                    continue
                if isinstance(x, str):
                    addressees.append(x)
                elif isinstance(x, list):
                    for item in x:
                        if isinstance(item, str):
                            addressees.append(item)
                        elif hasattr(item, "id_"):
                            addressees.append(item.id_)
                elif hasattr(x, "id_"):
                    addressees.append(x.id_)

            # Unique addressees, excluding the sending actor itself so
            # we don't deliver the notification back to our own inbox.
            addressees = [a for a in set(addressees) if a != self.actor_id]
            self.logger.info(
                f"{self.name}: Notifying addressees: {addressees}"
            )

            # Read full case to embed in the activity so recipients can
            # store the case object and process it without a separate fetch.
            case_obj = self.datalayer.read(case_id)

            # Create CreateCaseActivity activity domain object; embed the
            # full case as object_ so the inbox endpoint on the receiving
            # side stores the case before dispatching the activity.
            create_case_activity = VultronCreateCaseActivity(
                actor=self.actor_id,
                object_=case_obj if case_obj is not None else case_id,
                to=addressees if addressees else None,
            )

            # Store activity in DataLayer
            try:
                self.datalayer.create(create_case_activity)
                self.logger.info(
                    f"{self.name}: Created CreateCaseActivity activity: {create_case_activity.id_}"
                )
            except ValueError as e:
                self.logger.warning(
                    f"{self.name}: CreateCaseActivity activity {create_case_activity.id_} already exists: {e}"
                )

            # Store activity_id in blackboard for UpdateActorOutbox node
            self.blackboard.register_key(
                key="activity_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.activity_id = create_case_activity.id_

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
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
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

            case_id = self.blackboard.get("case_id")

            # Read actor
            actor_obj = self.datalayer.read(
                self.actor_id, raise_on_missing=True
            )

            # Verify actor has outbox
            if not has_outbox(actor_obj):
                self.logger.error(
                    f"{self.name}: Actor {self.actor_id} has no outbox or outbox.items"
                )
                return Status.FAILURE

            # Append activity to outbox (history for outbox_ids detection)
            actor_obj.outbox.items.append(activity_id)

            # Persist updated actor
            self.datalayer.save(actor_obj)

            # Also queue for delivery via outbox_handler
            self.datalayer.record_outbox_item(self.actor_id, activity_id)
            self.logger.info(
                "Queued Create(Case '%s') activity '%s' to actor '%s' outbox"
                " (case creation notification)",
                case_id,
                activity_id,
                self.actor_id,
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
            if not is_case_model(case_obj):
                self.logger.debug(
                    f"{self.name}: Case {self.case_id} not found"
                )
                return Status.FAILURE

            for participant_ref in case_obj.case_participants:
                if isinstance(participant_ref, str):
                    participant_raw = self.datalayer.read(participant_ref)
                    if participant_raw is None:
                        continue
                else:
                    participant_raw = participant_ref
                if not is_participant_model(participant_raw):
                    continue
                participant = participant_raw
                actor_ref = participant.attributed_to
                p_actor_id = (
                    actor_ref
                    if isinstance(actor_ref, str)
                    else getattr(actor_ref, "id_", str(actor_ref))
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

        try:
            if self.actor_id is None:
                self.logger.error(f"{self.name}: actor_id not available")
                return Status.FAILURE
            result = update_participant_rm_state(
                self.case_id, self.actor_id, RM.ACCEPTED, self.datalayer
            )
            return Status.SUCCESS if result else Status.FAILURE
        except Exception as e:
            self.logger.error(f"Error updating participant RM state: {e}")
            return Status.FAILURE


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

        try:
            if self.actor_id is None:
                self.logger.error(f"{self.name}: actor_id not available")
                return Status.FAILURE
            result = update_participant_rm_state(
                self.case_id, self.actor_id, RM.DEFERRED, self.datalayer
            )
            return Status.SUCCESS if result else Status.FAILURE
        except Exception as e:
            self.logger.error(f"Error updating participant RM state: {e}")
            return Status.FAILURE


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
