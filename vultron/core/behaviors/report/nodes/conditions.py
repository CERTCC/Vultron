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

"""Condition nodes for the report behavior tree."""

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerCondition,
    FindParticipantByActorIdNode,
)
from vultron.core.states.rm import RM
from vultron.core.models._helpers import _report_phase_status_id
from vultron.errors import VultronInvalidStateTransitionError


class CheckRMStateValid(DataLayerCondition):
    """
    Check if report is already in RM.VALID state.

    Returns SUCCESS if report status is RM.VALID (early exit optimization).
    Returns FAILURE if report is in any other state.

    This node implements the early-exit check from the simulation BT.
    """

    def __init__(
        self,
        report_id: str,
        sender_actor_id: str | None = None,
        name: str | None = None,
    ):
        """
        Initialize CheckRMStateValid node.

        Args:
            report_id: ID of VulnerabilityReport to check
            sender_actor_id: Explicit actor ID to use instead of the blackboard
                ``actor_id``.  Thread this in when the tree runs under
                ``receiving_actor_id`` but the RM check must target the message
                sender (ADR-0022 single-BT pattern).
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.sender_actor_id = sender_actor_id

    def update(self) -> Status:
        """
        Check if report is in RM.VALID state.

        Returns:
            SUCCESS if report is RM.VALID, FAILURE otherwise
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        actor_id = (
            self.sender_actor_id if self.sender_actor_id else self.actor_id
        )
        if actor_id is None:
            self.logger.error(f"{self.name}: actor_id not available")
            return Status.FAILURE

        valid_id = _report_phase_status_id(
            actor_id, self.report_id, RM.VALID.value
        )
        if self.datalayer.read(valid_id) is not None:
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

    def __init__(
        self,
        report_id: str,
        sender_actor_id: str | None = None,
        name: str | None = None,
    ):
        """
        Initialize CheckRMStateReceivedOrInvalid node.

        Args:
            report_id: ID of VulnerabilityReport to check
            sender_actor_id: Explicit actor ID to use instead of the blackboard
                ``actor_id``.  Thread this in when the tree runs under
                ``receiving_actor_id`` but the RM check must target the message
                sender (ADR-0022 single-BT pattern).
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.sender_actor_id = sender_actor_id

    def update(self) -> Status:
        """
        Check if report is in RM.RECEIVED or RM.INVALID state.

        Returns:
            SUCCESS if report is in acceptable state, FAILURE otherwise
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        actor_id = (
            self.sender_actor_id if self.sender_actor_id else self.actor_id
        )
        if actor_id is None:
            self.logger.error(f"{self.name}: actor_id not available")
            return Status.FAILURE

        valid_id = _report_phase_status_id(
            actor_id, self.report_id, RM.VALID.value
        )
        if self.datalayer.read(valid_id) is not None:
            self.logger.debug(
                f"{self.name}: Report {self.report_id} already VALID - precondition failed"
            )
            return Status.FAILURE

        self.logger.debug(
            f"{self.name}: Report {self.report_id} in acceptable state for validation"
        )
        return Status.SUCCESS


class EnsureEmbargoExists(DataLayerCondition):
    """
    Check that the case linked to this report has an active embargo.

    Returns SUCCESS if the case exists and has a non-None ``active_embargo``.
    Returns FAILURE if the case is not found or its ``active_embargo`` is None.

    This node implements DUR-07-004: an embargo end time MUST be established
    before the case reaches RM.VALID. It runs after ``TransitionRMtoValid``
    in ``ValidationActions`` to confirm that the default embargo seeded at
    RM.RECEIVED (DUR-07-002, via ``InitializeDefaultEmbargoNode``) is
    present before validation completes.
    """

    def __init__(self, report_id: str, name: str | None = None):
        """
        Initialize EnsureEmbargoExists node.

        Args:
            report_id: ID of VulnerabilityReport whose linked case to check
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        """
        Verify the case linked to this report has an active embargo.

        Returns:
            SUCCESS if case has active_embargo, FAILURE otherwise
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case = self.datalayer.find_case_by_report_id(self.report_id)
        if case is None:
            self.logger.warning(
                "%s: No case found for report %s",
                self.name,
                self.report_id,
            )
            return Status.FAILURE

        if getattr(case, "active_embargo", None) is None:
            self.logger.warning(
                "%s: Case for report %s has no active embargo — "
                "validation blocked (DUR-07-004)",
                self.name,
                self.report_id,
            )
            return Status.FAILURE

        self.logger.debug(
            "%s: Case for report %s has active embargo",
            self.name,
            self.report_id,
        )
        return Status.SUCCESS


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


class EvaluateCasePriority(DataLayerCondition):
    """
    Evaluate whether to engage or defer a case using prioritization policy.

    Phase 1: Always returns SUCCESS (stub — always engage).
    Future: Plug in SSVC or other priority framework via PrioritizationPolicy.

    This node is used when the local actor is DECIDING whether to engage or
    defer (i.e., generating an outgoing RmEngageCaseActivity or
    RmDeferCaseActivity message), as opposed to the receive-side nodes above
    which record a decision already made by the sending actor.

    See specs/prototype-shortcuts.yaml PROTO-05-001 for SSVC deferral policy.
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


class CheckParticipantExists(FindParticipantByActorIdNode):
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
        super().__init__(
            case_id=case_id,
            target_actor_id=actor_id,
            participant_key="participant",
            name=name or self.__class__.__name__,
        )


class CheckReportNotClosed(DataLayerCondition):
    """Check that the report does NOT already have an RM.CLOSED status record.

    Returns SUCCESS when the report is not yet closed (the transition is
    permitted).  Returns FAILURE and writes a
    :class:`~vultron.errors.VultronInvalidStateTransitionError` into
    ``result_out["error"]`` when the report is already closed, so the calling
    use case can re-raise the domain exception.

    Per issue #849 AC-3: the duplicate-close guard must be expressed as a BT
    condition node, not as a procedural raise in ``execute()``.
    """

    def __init__(
        self,
        report_id: str,
        result_out: dict,
        name: str | None = None,
    ) -> None:
        """Initialize CheckReportNotClosed.

        Args:
            report_id: ID of the VulnerabilityReport to check.
            result_out: Mutable dict; on FAILURE, the
                ``VultronInvalidStateTransitionError`` is written to
                ``result_out["error"]`` so the use case can re-raise it.
            name: Optional custom node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self._result_out = result_out

    def update(self) -> Status:
        """Guard against closing an already-closed report.

        Returns:
            SUCCESS when not yet closed;
            FAILURE (+ ``result_out["error"]``) when already closed or
            the DataLayer/actor_id is unavailable.
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if self.actor_id is None:
            self.logger.error("%s: actor_id not available", self.name)
            return Status.FAILURE

        closed_id = _report_phase_status_id(
            self.actor_id, self.report_id, RM.CLOSED.value
        )
        if self.datalayer.read(closed_id) is not None:
            error = VultronInvalidStateTransitionError(
                f"Report '{self.report_id}' is already CLOSED."
            )
            self._result_out["error"] = error
            self.feedback_message = str(error)
            self.logger.warning(
                "%s: Report '%s' is already CLOSED — transition blocked",
                self.name,
                self.report_id,
            )
            return Status.FAILURE

        self.logger.debug(
            "%s: Report '%s' not yet closed — proceeding",
            self.name,
            self.report_id,
        )
        return Status.SUCCESS
