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
Class-based use cases for report-level trigger behaviors.

Each class accepts a ``DataLayer`` and ``request`` at construction time and
exposes a single ``execute()`` method.  Helper function
``_resolve_offer_and_report`` is kept at module level because it may be
shared by multiple classes.

No HTTP framework imports (FastAPI, Starlette) are permitted here.
"""

import logging
from typing import TYPE_CHECKING, Any

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.report.trigger_report_trees import (
    create_close_report_trigger_tree,
    create_invalidate_report_trigger_tree,
    create_reject_report_trigger_tree,
)
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_tree,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.report import VultronReport
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases.triggers._helpers import (
    add_activity_to_outbox,
    outbox_ids,
    resolve_actor,
)
from vultron.core.use_cases.triggers.requests import (
    CloseReportTriggerRequest,
    InvalidateReportTriggerRequest,
    RejectReportTriggerRequest,
    SubmitReportTriggerRequest,
    ValidateReportTriggerRequest,
)
from vultron.errors import (
    VultronNotFoundError,
    VultronValidationError,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


def _resolve_offer_and_report(
    offer_id: str, dl: CaseOutboxPersistence
) -> tuple[Any, Any]:
    """Resolve offer and its embedded report; raise domain errors on failure.

    After the DataLayer rehydration pipeline, ``dl.read(offer_id)`` returns an
    ``RmSubmitReportActivity`` with its ``object_`` already expanded to a
    ``VulnerabilityReport``.  No manual coercion is needed.
    """
    offer = dl.read(offer_id)
    if offer is None:
        raise VultronNotFoundError("Offer", offer_id)
    if getattr(offer, "type_", "") != "Offer":
        raise VultronValidationError(
            f"Expected RmSubmitReportActivity for offer '{offer_id}', "
            f"got type '{getattr(offer, 'type_', 'unknown')}'."
        )
    report = getattr(offer, "object_", None)
    if getattr(report, "type_", "") != "VulnerabilityReport":
        raise VultronValidationError(
            f"Expected VulnerabilityReport embedded in offer '{offer_id}', "
            f"got type"
            f" '{getattr(report, 'type_', 'None' if report is None else 'unknown')}'."
        )
    return offer, report


class SvcValidateReportUseCase:
    """Validate a report offer using the ValidateReportBT behavior tree."""

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: ValidateReportTriggerRequest,
        sync_port: "SyncActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: ValidateReportTriggerRequest = request
        self._sync_port = sync_port

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        offer_id = request.offer_id
        note = request.note
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        offer, report = _resolve_offer_and_report(offer_id, dl)
        report_id = report.id_
        offer_id = offer.id_

        before = outbox_ids(actor_id, dl)

        bridge = BTBridge(datalayer=dl)
        tree = create_validate_report_tree(
            report_id=report_id,
            offer_id=offer_id,
        )

        context: dict[str, Any] = {}
        if note:
            context["note"] = note

        bridge.execute_with_setup(tree, actor_id=actor_id, **context)

        activity = None
        actor_after = dl.read(actor_id)
        if actor_after is not None:
            after = outbox_ids(actor_id, dl)
            new_items = after - before
            if new_items:
                activity_id = next(iter(new_items))
                activity_obj = dl.read(activity_id)
                if activity_obj is not None:
                    activity = activity_obj.model_dump(
                        by_alias=True, exclude_none=True
                    )

        self._commit_validate_report_log(
            report_id=report_id, offer_id=offer_id
        )

        return {"activity": activity}

    def _commit_validate_report_log(
        self, *, report_id: str, offer_id: str
    ) -> None:
        """Commit a canonical case ledger entry for this validate_report step.

        Finds the case associated with the report and the CaseActor, then
        commits a ``validate_report`` ledger entry on behalf of the CaseActor.
        """
        from vultron.core.use_cases._helpers import (
            build_activity_payload_snapshot,
        )
        from vultron.core.use_cases.received.actor import _find_case_actor_id
        from vultron.core.use_cases.triggers.sync import (
            commit_log_entry_trigger,
        )

        dl = self._dl
        case = dl.find_case_by_report_id(report_id)
        if case is None:
            logger.warning(
                "validate_report: cannot find case for report '%s'"
                " — skipping ledger entry",
                report_id,
            )
            return

        case_id = getattr(case, "id_", None)
        if case_id is None:
            logger.warning(
                "validate_report: case for report '%s' has no id_"
                " — skipping ledger entry",
                report_id,
            )
            return

        case_actor_id = _find_case_actor_id(dl, case_id)
        if case_actor_id is None:
            logger.warning(
                "validate_report: cannot resolve CaseActor for case '%s'"
                " — skipping ledger entry",
                case_id,
            )
            return

        offer = dl.read(offer_id)
        payload_snapshot = build_activity_payload_snapshot(offer, dl=dl)

        commit_log_entry_trigger(
            case_id=case_id,
            object_id=offer_id,
            event_type="validate_report",
            actor_id=case_actor_id,
            dl=dl,
            sync_port=self._sync_port,
            payload_snapshot=payload_snapshot,
        )


class SvcInvalidateReportUseCase:
    """Emit RmInvalidateReportActivity (TentativeReject) for the given offer."""

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: InvalidateReportTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: InvalidateReportTriggerRequest = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        offer_id = request.offer_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        offer, report = _resolve_offer_and_report(offer_id, dl)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcInvalidateReportUseCase requires a TriggerActivityPort"
            )

        before = outbox_ids(actor_id, dl)

        bridge = BTBridge(
            datalayer=dl, trigger_activity=self._trigger_activity
        )
        tree = create_invalidate_report_trigger_tree(
            offer_id=offer.id_,
            report_id=report.id_,
        )
        result = bridge.execute_with_setup(tree, actor_id=actor_id)
        if result.status != Status.SUCCESS:
            raise VultronValidationError(
                f"InvalidateReport failed: {BTBridge.get_failure_reason(tree)}"
            )

        activity = None
        after = outbox_ids(actor_id, dl)
        new_items = after - before
        if new_items:
            activity_id = next(iter(new_items))
            activity_obj = dl.read(activity_id)
            if activity_obj is not None:
                activity = activity_obj.model_dump(
                    by_alias=True, exclude_none=True
                )

        logger.info(
            "Actor '%s' invalidated offer '%s' (report '%s')",
            actor_id,
            offer.id_,
            report.id_,
        )

        return {"activity": activity}


class SvcRejectReportUseCase:
    """Hard-close a report offer by emitting RmCloseReportActivity (Reject)."""

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: RejectReportTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: RejectReportTriggerRequest = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        offer_id = request.offer_id
        note = request.note
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        offer, report = _resolve_offer_and_report(offer_id, dl)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcRejectReportUseCase requires a TriggerActivityPort"
            )

        before = outbox_ids(actor_id, dl)

        bridge = BTBridge(
            datalayer=dl, trigger_activity=self._trigger_activity
        )
        tree = create_reject_report_trigger_tree(
            offer_id=offer.id_,
            report_id=report.id_,
        )
        result = bridge.execute_with_setup(tree, actor_id=actor_id)
        if result.status != Status.SUCCESS:
            raise VultronValidationError(
                f"RejectReport failed: {BTBridge.get_failure_reason(tree)}"
            )

        activity = None
        after = outbox_ids(actor_id, dl)
        new_items = after - before
        if new_items:
            activity_id = next(iter(new_items))
            activity_obj = dl.read(activity_id)
            if activity_obj is not None:
                activity = activity_obj.model_dump(
                    by_alias=True, exclude_none=True
                )

        logger.info(
            "Actor '%s' hard-closed offer '%s' (report '%s'); note: %s",
            actor_id,
            offer.id_,
            report.id_,
            note,
        )

        return {"activity": activity}


class SvcCloseReportUseCase:
    """Close a report via the RM lifecycle (RM → C transition)."""

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: CloseReportTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: CloseReportTriggerRequest = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        offer_id = request.offer_id
        note = request.note
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        offer, report = _resolve_offer_and_report(offer_id, dl)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcCloseReportUseCase requires a TriggerActivityPort"
            )

        before = outbox_ids(actor_id, dl)
        result_out: dict[str, object] = {}

        bridge = BTBridge(
            datalayer=dl, trigger_activity=self._trigger_activity
        )
        tree = create_close_report_trigger_tree(
            offer_id=offer.id_,
            report_id=report.id_,
            result_out=result_out,
        )
        result = bridge.execute_with_setup(tree, actor_id=actor_id)
        if result.status != Status.SUCCESS:
            error = result_out.get("error")
            if isinstance(error, Exception):
                raise error
            raise VultronValidationError(
                f"CloseReport failed: {BTBridge.get_failure_reason(tree)}"
            )

        activity = None
        after = outbox_ids(actor_id, dl)
        new_items = after - before
        if new_items:
            activity_id = next(iter(new_items))
            activity_obj = dl.read(activity_id)
            if activity_obj is not None:
                activity = activity_obj.model_dump(
                    by_alias=True, exclude_none=True
                )

        logger.info(
            "Actor '%s' closed offer '%s' (report '%s') via RM lifecycle;"
            " note: %s",
            actor_id,
            offer.id_,
            report.id_,
            note,
        )

        return {"activity": activity}


class SvcSubmitReportUseCase:
    """Create a VulnerabilityReport and offer it to a recipient.

    Stores the report and an RmSubmitReportActivity in the actor's DataLayer,
    queues the offer in the actor's outbox, and returns the serialised offer so
    the caller can deliver it (e.g. POST to the recipient's inbox).
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: SubmitReportTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        dl = self._dl

        actor = resolve_actor(request.actor_id, dl)
        actor_id = actor.id_

        report = VultronReport(
            name=request.report_name,
            content=request.report_content,
            attributed_to=actor_id,
        )
        try:
            dl.create(report)
        except ValueError:
            logger.warning(
                "VulnerabilityReport '%s' already exists", report.id_
            )

        logger.info(
            "Created VulnerabilityReport '%s' (id: '%s')",
            request.report_name,
            report.id_,
        )
        try:
            dl.create(
                VultronReportCaseLink(
                    report_id=report.id_,
                    trusted_case_creator_id=request.recipient_id,
                )
            )
        except ValueError:
            logger.debug(
                "SvcSubmitReportUseCase: ReportCaseLink for '%s' already "
                "exists — preserving existing link (idempotent)",
                report.id_,
            )

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcSubmitReportUseCase requires a TriggerActivityPort"
            )

        offer_id, offer_dict = self._trigger_activity.submit_report(
            report_id=report.id_,
            actor=actor_id,
            to=request.recipient_id,
            target=request.recipient_id,
        )

        logger.info(
            "Offering report '%s' to '%s' (offer: '%s')",
            report.id_,
            request.recipient_id,
            offer_id,
        )

        add_activity_to_outbox(actor_id, offer_id, dl)

        return {"offer": offer_dict}
