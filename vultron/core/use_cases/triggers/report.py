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
from typing import Any, cast

import py_trees.behaviour

from vultron.core.behaviors.report.trigger_report_trees import (
    create_close_report_trigger_tree,
    create_invalidate_report_trigger_tree,
    create_reject_report_trigger_tree,
    submit_report_trigger_bt,
)
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_tree,
)
from vultron.core.models.report import VultronReport
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import (
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
from vultron.errors import VultronNotFoundError, VultronValidationError

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


class SvcValidateReportUseCase(SvcBTTriggerBase):
    """Validate a report offer using the ValidateReportBT behavior tree.

    Does not require a TriggerActivityPort — the validate BT performs only
    state transitions without constructing outbound activities.
    The BT also commits a ``validate_report`` canonical ledger entry via
    ``create_commit_log_entry_tree`` (BT-15-001).
    """

    _requires_trigger_activity = False

    def _prepare(self) -> None:
        from vultron.core.use_cases._helpers import (
            build_activity_payload_snapshot,
        )

        request = cast(ValidateReportTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._offer, self._report = _resolve_offer_and_report(
            request.offer_id, self._dl
        )
        self._before = outbox_ids(self._actor_id, self._dl)
        case = self._dl.find_case_by_report_id(self._report.id_)
        self._case_id: str | None = getattr(case, "id_", None)
        self._payload_snapshot = build_activity_payload_snapshot(
            self._offer, dl=self._dl
        )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return create_validate_report_tree(
            report_id=self._report.id_,
            offer_id=self._offer.id_,
            case_id=self._case_id,
            payload_snapshot=self._payload_snapshot,
        )

    def _handle_result(self) -> None:
        after = outbox_ids(self._actor_id, self._dl)
        new_items = after - self._before
        if new_items:
            activity_id = next(iter(new_items))
            activity_obj = self._dl.read(activity_id)
            if activity_obj is not None:
                self._captured["activity"] = activity_obj.model_dump(
                    by_alias=True, exclude_none=True
                )


class SvcInvalidateReportUseCase(SvcBTTriggerBase):
    """Emit RmInvalidateReportActivity (TentativeReject) for the given offer."""

    def _prepare(self) -> None:
        request = cast(InvalidateReportTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._offer, self._report = _resolve_offer_and_report(
            request.offer_id, self._dl
        )
        self._before = outbox_ids(self._actor_id, self._dl)

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return create_invalidate_report_trigger_tree(
            offer_id=self._offer.id_,
            report_id=self._report.id_,
        )

    def _handle_result(self) -> None:
        after = outbox_ids(self._actor_id, self._dl)
        new_items = after - self._before
        if new_items:
            activity_id = next(iter(new_items))
            activity_obj = self._dl.read(activity_id)
            if activity_obj is not None:
                self._captured["activity"] = activity_obj.model_dump(
                    by_alias=True, exclude_none=True
                )
        logger.info(
            "Actor '%s' invalidated offer '%s' (report '%s')",
            self._actor_id,
            self._offer.id_,
            self._report.id_,
        )


class SvcRejectReportUseCase(SvcBTTriggerBase):
    """Hard-close a report offer by emitting RmCloseReportActivity (Reject)."""

    def _prepare(self) -> None:
        request = cast(RejectReportTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._offer, self._report = _resolve_offer_and_report(
            request.offer_id, self._dl
        )
        self._before = outbox_ids(self._actor_id, self._dl)

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return create_reject_report_trigger_tree(
            offer_id=self._offer.id_,
            report_id=self._report.id_,
        )

    def _handle_result(self) -> None:
        after = outbox_ids(self._actor_id, self._dl)
        new_items = after - self._before
        if new_items:
            activity_id = next(iter(new_items))
            activity_obj = self._dl.read(activity_id)
            if activity_obj is not None:
                self._captured["activity"] = activity_obj.model_dump(
                    by_alias=True, exclude_none=True
                )
        request = cast(RejectReportTriggerRequest, self._request)
        logger.info(
            "Actor '%s' hard-closed offer '%s' (report '%s'); note: %s",
            self._actor_id,
            self._offer.id_,
            self._report.id_,
            request.note,
        )


class SvcCloseReportUseCase(SvcBTTriggerBase):
    """Close a report via the RM lifecycle (RM → C transition)."""

    def _prepare(self) -> None:
        request = cast(CloseReportTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._offer, self._report = _resolve_offer_and_report(
            request.offer_id, self._dl
        )
        self._before = outbox_ids(self._actor_id, self._dl)

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return create_close_report_trigger_tree(
            offer_id=self._offer.id_,
            report_id=self._report.id_,
            result_out=self._result_out,
        )

    def _handle_result(self) -> None:
        after = outbox_ids(self._actor_id, self._dl)
        new_items = after - self._before
        if new_items:
            activity_id = next(iter(new_items))
            activity_obj = self._dl.read(activity_id)
            if activity_obj is not None:
                self._captured["activity"] = activity_obj.model_dump(
                    by_alias=True, exclude_none=True
                )
        request = cast(CloseReportTriggerRequest, self._request)
        logger.info(
            "Actor '%s' closed offer '%s' (report '%s') via RM lifecycle;"
            " note: %s",
            self._actor_id,
            self._offer.id_,
            self._report.id_,
            request.note,
        )


class SvcSubmitReportUseCase(SvcBTTriggerBase):
    """Create a VulnerabilityReport and offer it to a recipient.

    Stores the report and a VultronReportCaseLink in the actor's DataLayer
    during ``_prepare()``, then runs ``SubmitReportTriggerBT`` to build
    and queue the Offer activity.  Returns ``{"offer": <offer_dict>}``
    rather than the base-class ``{"activity": ...}`` shape to preserve
    the existing API contract.
    """

    def _prepare(self) -> None:
        request = cast(SubmitReportTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_

        report = VultronReport(
            name=request.report_name,
            content=request.report_content,
            attributed_to=self._actor_id,
        )
        try:
            self._dl.create(report)
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
            self._dl.create(
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

        self._report_id = report.id_
        self._recipient_id = request.recipient_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return submit_report_trigger_bt(
            report_id=self._report_id,
            recipient_id=self._recipient_id,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Offering report '%s' to '%s'",
            self._report_id,
            self._recipient_id,
        )

    def execute(self) -> dict:
        """Execute and return ``{"offer": <offer_dict>}``."""
        super().execute()
        return {"offer": self._captured.get("offer")}
