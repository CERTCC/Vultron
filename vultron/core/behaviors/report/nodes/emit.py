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
from vultron.core.use_cases._helpers import _resolve_case_manager_id


def _compute_report_addressees(
    report_id: str,
    actor_id: str,
    offer: object | None,
    dl: CaseOutboxPersistence,
) -> list[str] | None:
    """Compute outbound recipient list for a report-phase trigger activity.

    For case-scoped report activities, route only to the Case Actor. Falls back
    to the offer submitter when no case is found (no case-scoped routing).

    Args:
        report_id: VulnerabilityReport ID used to locate the linked case.
        actor_id: Sender's actor ID (excluded from recipient list).
        offer: The Offer activity object (used for fallback addressing).
        dl: DataLayer for case lookup.

    Returns:
        List of recipient URIs, or None when no recipients can be determined.
    """
    case = dl.find_case_by_report_id(report_id)
    if is_case_model(case):
        case_manager_id = _resolve_case_manager_id(case, dl)
        if case_manager_id and case_manager_id != actor_id:
            return [case_manager_id]
        return None

    offer_actor = getattr(offer, "actor", None)
    if offer_actor is None:
        return None
    offer_actor_id = (
        offer_actor
        if isinstance(offer_actor, str)
        else getattr(offer_actor, "id_", None)
    )
    if offer_actor_id and offer_actor_id != actor_id:
        return [offer_actor_id]
    return None


class EmitInvalidateReportActivity(DataLayerAction):
    """Emit RmInvalidateReportActivity (TentativeReject) to the actor outbox.

    Calls ``trigger_activity_factory.invalidate_report()`` and queues the
    resulting activity ID via ``record_outbox_item``.

    Per issue #849 AC-1, AC-2: emit nodes must be BT leaf nodes, not inline
    procedural calls in ``execute()``.
    """

    def __init__(
        self, offer_id: str, report_id: str, name: str | None = None
    ) -> None:
        """Initialize EmitInvalidateReportActivity.

        Args:
            offer_id: ID of the Offer activity being invalidated.
            report_id: ID of the VulnerabilityReport (for address resolution).
            name: Optional custom node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.offer_id = offer_id
        self.report_id = report_id

    def update(self) -> Status:
        """Create and queue RmInvalidateReportActivity.

        Returns:
            SUCCESS if activity created and outbox updated, FAILURE on error.
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        if self.trigger_activity_factory is None:
            self.logger.warning(
                "%s: no TriggerActivityPort — cannot emit InvalidateReport activity",
                self.name,
            )
            return Status.FAILURE

        try:
            offer = self.datalayer.read(self.offer_id)
            addressees = _compute_report_addressees(
                self.report_id,
                self.actor_id,
                offer,
                cast(CaseOutboxPersistence, self.datalayer),
            )
            if not addressees:
                self.logger.error(
                    "%s: no routable recipients for report activity"
                    " (offer_id=%s, report_id=%s, actor_id=%s)",
                    self.name,
                    self.offer_id,
                    self.report_id,
                    self.actor_id,
                )
                return Status.FAILURE

            activity_id, _ = self.trigger_activity_factory.invalidate_report(
                offer_id=self.offer_id,
                actor=self.actor_id,
                to=addressees,
            )

            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            self.logger.info(
                "Actor '%s' emitted RmInvalidateReportActivity for offer '%s'",
                self.actor_id,
                self.offer_id,
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                "%s: Error emitting invalidate-report activity: %s",
                self.name,
                e,
            )
            return Status.FAILURE


class EmitCloseReportActivity(DataLayerAction):
    """Emit RmCloseReportActivity (Reject) to the actor outbox.

    Calls ``trigger_activity_factory.close_report()`` and queues the
    resulting activity ID via ``record_outbox_item``.

    Used by both the reject-report and close-report trigger workflows.

    Per issue #849 AC-1, AC-2: emit nodes must be BT leaf nodes, not inline
    procedural calls in ``execute()``.
    """

    def __init__(
        self, offer_id: str, report_id: str, name: str | None = None
    ) -> None:
        """Initialize EmitCloseReportActivity.

        Args:
            offer_id: ID of the Offer activity being closed/rejected.
            report_id: ID of the VulnerabilityReport.
            name: Optional custom node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.offer_id = offer_id
        self.report_id = report_id

    def update(self) -> Status:
        """Create and queue RmCloseReportActivity.

        Returns:
            SUCCESS if activity created and outbox updated, FAILURE on error.
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        if self.trigger_activity_factory is None:
            self.logger.warning(
                "%s: no TriggerActivityPort — cannot emit CloseReport activity",
                self.name,
            )
            return Status.FAILURE

        try:
            offer = self.datalayer.read(self.offer_id)
            addressees = _compute_report_addressees(
                self.report_id,
                self.actor_id,
                offer,
                cast(CaseOutboxPersistence, self.datalayer),
            )
            if not addressees:
                self.logger.error(
                    "%s: no routable recipients for report activity"
                    " (offer_id=%s, report_id=%s, actor_id=%s)",
                    self.name,
                    self.offer_id,
                    self.report_id,
                    self.actor_id,
                )
                return Status.FAILURE

            activity_id, _ = self.trigger_activity_factory.close_report(
                offer_id=self.offer_id,
                report_id=self.report_id,
                actor=self.actor_id,
                to=addressees,
            )

            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            self.logger.info(
                "Actor '%s' emitted RmCloseReportActivity for offer '%s'",
                self.actor_id,
                self.offer_id,
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                "%s: Error emitting close-report activity: %s", self.name, e
            )
            return Status.FAILURE
