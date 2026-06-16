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

"""RM transition nodes for the report behavior tree."""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.protocols import is_case_model
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases._helpers import (
    _idempotent_create,
    _report_phase_status_id,
    update_participant_rm_state,
)


def _transition_case_participant_rm(
    node: "DataLayerAction",
    report_id: str | None,
    new_rm_state: RM,
) -> "Status":
    """Shared logic for case-participant RM transitions triggered by report.

    Finds the VulnerabilityCase associated with *report_id* and advances the
    actor's RM state in that case.

    Soft-passes (SUCCESS) when no report_id is provided or when no case is
    found for the report — matching the log-and-continue behavior of the
    original procedural handlers.  Returns FAILURE only when a case is found
    but ``update_participant_rm_state`` reports the transition was blocked.

    Args:
        node: Calling DataLayerAction node (provides datalayer and actor_id).
        report_id: ID of the VulnerabilityReport; may be None.
        new_rm_state: Target RM state to transition the participant to.

    Returns:
        SUCCESS or FAILURE (py_trees Status).
    """
    from py_trees.common import Status

    if not report_id:
        node.logger.debug(
            "%s: no report_id — skipping RM transition", node.name
        )
        return Status.SUCCESS

    if node.datalayer is None:
        node.logger.error("%s: DataLayer not available", node.name)
        return Status.FAILURE

    case = node.datalayer.find_case_by_report_id(report_id)
    if not is_case_model(case):
        node.logger.warning(
            "%s: no case found for report '%s' — RM state not updated",
            node.name,
            report_id,
        )
        return Status.SUCCESS

    actor_id = node.actor_id
    if actor_id is None:
        node.logger.error("%s: actor_id not set on blackboard", node.name)
        return Status.FAILURE

    ok = update_participant_rm_state(
        case.id_, actor_id, new_rm_state, node.datalayer
    )
    if not ok:
        node.logger.warning(
            "%s: RM transition to %s blocked for actor '%s' in case '%s'",
            node.name,
            new_rm_state,
            actor_id,
            case.id_,
        )
        return Status.FAILURE

    return Status.SUCCESS


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

        Creates a standalone ParticipantStatus record for RM.VALID and
        also updates the CaseParticipant.participant_statuses list (via
        ``update_participant_rm_state``) so that the engage-case trigger can
        advance to RM.ACCEPTED from VALID rather than RECEIVED.

        Returns:
            SUCCESS if status updated, FAILURE on error
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            # CLP-07-007: context must use the case URI once a case exists.
            case = self.datalayer.find_case_by_report_id(self.report_id)
            context = case.id_ if is_case_model(case) else self.report_id

            status = ParticipantStatus(
                id_=_report_phase_status_id(
                    self.actor_id, self.report_id, RM.VALID.value
                ),
                context=context,
                attributed_to=self.actor_id,
                rm_state=RM.VALID,
                em_consent_state=PEC.NO_EMBARGO,
                cvd_role=[CVDRole.REPORTER],
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

            if is_case_model(case):
                update_participant_rm_state(
                    case.id_, self.actor_id, RM.VALID, self.datalayer
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
            # CLP-07-007: context must use the case URI once a case exists.
            case = self.datalayer.find_case_by_report_id(self.report_id)
            context = case.id_ if is_case_model(case) else self.report_id

            status = ParticipantStatus(
                id_=_report_phase_status_id(
                    self.actor_id, self.report_id, RM.INVALID.value
                ),
                context=context,
                attributed_to=self.actor_id,
                rm_state=RM.INVALID,
                em_consent_state=PEC.NO_EMBARGO,
                cvd_role=[CVDRole.REPORTER],
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


class TransitionRMtoClosed(DataLayerAction):
    """
    Transition report to RM.CLOSED (report-phase ParticipantStatus).

    Persists a ParticipantStatus record with RM.CLOSED for the actor and
    report in the DataLayer.
    Logs state transitions at INFO level.

    Used by both the reject-report and close-report trigger workflows.
    """

    def __init__(self, report_id: str, offer_id: str, name: str | None = None):
        """
        Initialize TransitionRMtoClosed node.

        Args:
            report_id: ID of VulnerabilityReport to update
            offer_id: ID of Offer being closed/rejected
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.offer_id = offer_id

    def update(self) -> Status:
        """
        Update report status to CLOSED in DataLayer.

        Returns:
            SUCCESS if status updated, FAILURE on error
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        try:
            # CLP-07-007: context must use the case URI once a case exists.
            case = self.datalayer.find_case_by_report_id(self.report_id)
            context = case.id_ if is_case_model(case) else self.report_id

            status = ParticipantStatus(
                id_=_report_phase_status_id(
                    self.actor_id, self.report_id, RM.CLOSED.value
                ),
                context=context,
                attributed_to=self.actor_id,
                rm_state=RM.CLOSED,
                em_consent_state=PEC.NO_EMBARGO,
                cvd_role=[CVDRole.REPORTER],
            )
            _idempotent_create(
                self.datalayer,
                "ParticipantStatus",
                status.id_,
                status,
                "ParticipantStatus (report-phase RM.CLOSED)",
            )
            self.logger.info(
                "RM → CLOSED for report '%s' (actor '%s')",
                self.report_id,
                self.actor_id,
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                "%s: Error transitioning to CLOSED: %s", self.name, e
            )
            return Status.FAILURE


class TransitionCaseParticipantRMtoClosed(DataLayerAction):
    """Transition the actor's RM state to CLOSED in the case for a report.

    Looks up the VulnerabilityCase by ``report_id`` and advances the actor's
    RM state to ``RM.CLOSED`` via ``update_participant_rm_state``.

    Soft-passes (SUCCESS) when no ``report_id`` is set or no case is found,
    matching the log-and-continue behavior of ``CloseReportReceivedUseCase``.
    """

    def __init__(self, report_id: str | None, name: str | None = None):
        """Initialize TransitionCaseParticipantRMtoClosed.

        Args:
            report_id: ID of the VulnerabilityReport whose case should be
                updated; may be None for a no-op soft pass.
            name: Optional custom node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        """Transition participant RM state → CLOSED.

        Returns:
            SUCCESS if transitioned (or no case found — soft pass);
            FAILURE if the DataLayer is unavailable or the transition is
            blocked.
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        return _transition_case_participant_rm(self, self.report_id, RM.CLOSED)


class TransitionCaseParticipantRMtoInvalid(DataLayerAction):
    """Transition the actor's RM state to INVALID in the case for a report.

    Looks up the VulnerabilityCase by ``report_id`` and advances the actor's
    RM state to ``RM.INVALID`` via ``update_participant_rm_state``.

    Soft-passes (SUCCESS) when no ``report_id`` is set or no case is found,
    matching the log-and-continue behavior of ``InvalidateReportReceivedUseCase``.
    """

    def __init__(self, report_id: str | None, name: str | None = None):
        """Initialize TransitionCaseParticipantRMtoInvalid.

        Args:
            report_id: ID of the VulnerabilityReport whose case should be
                updated; may be None for a no-op soft pass.
            name: Optional custom node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        """Transition participant RM state → INVALID.

        Returns:
            SUCCESS if transitioned (or no case found — soft pass);
            FAILURE if the DataLayer is unavailable or the transition is
            blocked.
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        return _transition_case_participant_rm(
            self, self.report_id, RM.INVALID
        )
