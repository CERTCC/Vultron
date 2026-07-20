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
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases._helpers import _resolve_case_manager_id


class _EmitCaseActorReportActivityBase(DataLayerAction):
    """Base class for emit nodes that route report-phase activities to the CaseActor.

    Per ADR-0021 CLP-10-001: trigger trees MUST emit an outbound activity
    addressed to case_manager_id so the CaseActor receives it and can commit
    a canonical ledger entry.

    Subclasses must override ``_call_factory`` to invoke the appropriate
    ``TriggerActivityPort`` method and return ``(activity_id, activity_dict)``.
    """

    def __init__(
        self, offer_id: str, report_id: str, name: str | None = None
    ) -> None:
        """Initialize the base emit node.

        Args:
            offer_id: ID of the Offer activity being acted upon.
            report_id: ID of the VulnerabilityReport (for address resolution).
            name: Optional custom node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self.offer_id = offer_id
        self.report_id = report_id

    def _call_factory(
        self, actor_id: str, addressees: list[str]
    ) -> tuple[str, dict]:
        """Invoke the trigger-activity factory method for this activity type.

        Args:
            actor_id: Sending actor URI.
            addressees: Recipient URI list (already computed).

        Returns:
            ``(activity_id, activity_dict)``

        Raises:
            NotImplementedError: Subclasses must implement this method.
        """
        raise NotImplementedError

    def _compute_addressees(self) -> list[str] | None:
        """Resolve and validate outbound recipients; return None to fail."""
        assert self.datalayer is not None and self.actor_id is not None
        offer = self.datalayer.read(self.offer_id)
        addressees = _compute_report_addressees(
            self.report_id,
            self.actor_id,
            offer,
            cast(CaseOutboxPersistence, self.datalayer),
        )
        if not addressees:
            self.feedback_message = (
                f"no routable recipients for report activity"
                f" (offer_id={self.offer_id}, report_id={self.report_id},"
                f" actor_id={self.actor_id})"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
        return addressees

    def _validate_context(self) -> Status | None:
        if (f := self._require_datalayer_and_actor()) is not None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return f
        if (f := self._require_factory()) is not None:
            self.logger.warning(
                "%s: no TriggerActivityPort — cannot emit report activity",
                self.name,
            )
            return f
        return None

    def update(self) -> Status:
        """Create and queue the report-phase activity."""
        if (f := self._validate_context()) is not None:
            return f
        try:
            addressees = self._compute_addressees()
            if not addressees:
                return Status.FAILURE
            activity_id, _ = self._call_factory(self.actor_id, addressees)  # type: ignore[arg-type]
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id  # type: ignore[arg-type]
            )
            self.logger.info(
                "Actor '%s' emitted %s for offer '%s'",
                self.actor_id,
                self.__class__.__name__,
                self.offer_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.logger.error("%s: Error emitting activity: %s", self.name, e)
            return Status.FAILURE


class EmitValidateReportActivity(_EmitCaseActorReportActivityBase):
    """Emit RmValidateReportActivity to the Case Actor's inbox.

    Calls ``trigger_activity_factory.validate_report()`` and queues the
    resulting activity ID via ``record_outbox_item``. Routes the activity
    to the Case Actor (CASE_MANAGER participant) using ``_compute_report_addressees``.

    Per ADR-0021 CLP-10-001: trigger trees MUST emit an outbound activity
    addressed to case_manager_id so the CaseActor receives the activity and
    can execute the guarded commit.

    Per issue #1029 AC-1: validate_tree.py transitions from
    ``_requires_trigger_activity = False`` to having a proper emit node.
    """

    def _call_factory(
        self, actor_id: str, addressees: list[str]
    ) -> tuple[str, dict]:
        """Call ``validate_report`` on the trigger-activity factory."""
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.validate_report(
            offer_id=self.offer_id,
            report_id=self.report_id,
            actor=actor_id,
            to=addressees,
        )


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
    if isinstance(case, VulnerabilityCase):
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


class EmitInvalidateReportActivity(_EmitCaseActorReportActivityBase):
    """Emit RmInvalidateReportActivity (TentativeReject) to the actor outbox.

    Calls ``trigger_activity_factory.invalidate_report()`` and queues the
    resulting activity ID via ``record_outbox_item``.

    Per issue #849 AC-1, AC-2: emit nodes must be BT leaf nodes, not inline
    procedural calls in ``execute()``.
    """

    def _call_factory(
        self, actor_id: str, addressees: list[str]
    ) -> tuple[str, dict]:
        """Call ``invalidate_report`` on the trigger-activity factory."""
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.invalidate_report(
            offer_id=self.offer_id,
            actor=actor_id,
            to=addressees,
        )


class EmitCloseReportActivity(_EmitCaseActorReportActivityBase):
    """Emit RmCloseReportActivity (Reject) to the actor outbox.

    Calls ``trigger_activity_factory.close_report()`` and queues the
    resulting activity ID via ``record_outbox_item``.

    Used by both the reject-report and close-report trigger workflows.

    Per issue #849 AC-1, AC-2: emit nodes must be BT leaf nodes, not inline
    procedural calls in ``execute()``.
    """

    def _call_factory(
        self, actor_id: str, addressees: list[str]
    ) -> tuple[str, dict]:
        """Call ``close_report`` on the trigger-activity factory."""
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.close_report(
            offer_id=self.offer_id,
            report_id=self.report_id,
            actor=actor_id,
            to=addressees,
        )


class EmitAckReportActivity(_EmitCaseActorReportActivityBase):
    """Emit RmAckReportActivity (Read(Offer(Report))) to the CaseActor's inbox.

    Per ADR-0021 CLP-10-001: when a vendor acknowledges a report, the AckReport
    activity must be addressed to the CaseActor so the CaseActor can commit
    a canonical ledger entry.
    """

    def _call_factory(
        self, actor_id: str, addressees: list[str]
    ) -> tuple[str, dict]:
        """Call ``ack_report`` on the trigger-activity factory."""
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.ack_report(
            offer_id=self.offer_id,
            actor=actor_id,
            to=addressees,
        )


class EmitSubmitReportActivity(DataLayerAction):
    """Create Offer(VulnerabilityReport) and queue in actor outbox.

    Calls ``trigger_activity_factory.submit_report()`` and queues the
    offer ID via ``record_outbox_item``.  Stores the offer dict in
    ``captured["offer"]`` if *captured* is provided.

    Per BT-15-001: outbound activity construction and queueing must be
    BT leaf nodes.
    """

    def __init__(
        self,
        report_id: str,
        recipient_id: str,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.recipient_id = recipient_id
        self._captured = captured

    def _call_factory(self) -> tuple[str, dict]:
        """Call submit_report on the factory. Raises on error."""
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.submit_report(
            report_id=self.report_id,
            actor=self.actor_id,
            to=self.recipient_id,
            target=self.recipient_id,
        )

    def _validate_context(self) -> Status | None:
        if (f := self._require_datalayer_and_actor()) is not None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return f
        if (f := self._require_factory()) is not None:
            self.logger.warning(
                "%s: no TriggerActivityPort — cannot emit SubmitReport offer",
                self.name,
            )
            return f
        return None

    def update(self) -> Status:
        if (f := self._validate_context()) is not None:
            return f
        try:
            offer_id, offer_dict = self._call_factory()
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, offer_id  # type: ignore[arg-type]
            )
            if self._captured is not None:
                self._captured["offer"] = offer_dict
            self.logger.info(
                "Actor '%s' emitted Offer(VulnerabilityReport) '%s' to '%s'",
                self.actor_id,
                offer_id,
                self.recipient_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.logger.error(
                "%s: Error emitting submit-report offer: %s", self.name, e
            )
            return Status.FAILURE
