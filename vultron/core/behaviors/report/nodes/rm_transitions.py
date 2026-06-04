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
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import (
    _idempotent_create,
    _report_phase_status_id,
    update_participant_rm_state,
)


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
            status = ParticipantStatus(
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

            case = self.datalayer.find_case_by_report_id(self.report_id)
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
            status = ParticipantStatus(
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
