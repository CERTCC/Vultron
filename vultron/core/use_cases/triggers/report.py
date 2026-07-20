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
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report import VulnerabilityReport, VultronReport
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import (
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
) -> tuple[Any, VulnerabilityReport]:
    """Resolve the offer record and its embedded report from core state.

    Per ADR-0035 DL-06-001: core MUST NOT re-read the stored Offer wire
    activity to recover semantic content.  The domain facts (report ID,
    offer actor) are captured in a ``VultronOfferRecord`` at submission time.
    """
    record_id = VultronOfferRecord.build_id(offer_id)
    offer_record = dl.read(record_id)
    if offer_record is None:
        raise VultronNotFoundError("Offer", offer_id)
    if not isinstance(offer_record, VultronOfferRecord):
        raise VultronValidationError(
            f"Expected VultronOfferRecord for offer '{offer_id}', "
            f"got type '{getattr(offer_record, 'type_', 'unknown')}'."
        )
    report = dl.read(offer_record.report_id)
    if report is None:
        raise VultronNotFoundError(
            "VulnerabilityReport", offer_record.report_id
        )
    if not isinstance(report, VulnerabilityReport):
        raise VultronValidationError(
            f"Expected VulnerabilityReport '{offer_record.report_id}', "
            f"got type '{getattr(report, 'type_', 'unknown')}'."
        )
    return offer_record, report


class SvcValidateReportUseCase(SvcBTTriggerBase):
    """Validate a report offer using the ValidateReportBT behavior tree.

    Per ADR-0021 CLP-10-001: the validate trigger tree now emits an
    RmValidateReportActivity addressed to the Case Actor. This requires
    a TriggerActivityPort to construct the outbound activity.

    Per issue #1029 AC-1: no longer has ``_requires_trigger_activity = False``;
    the trigger_activity port is required.
    """

    def _prepare(self) -> None:
        request = cast(ValidateReportTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._offer, self._report = _resolve_offer_and_report(
            request.offer_id, self._dl
        )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return create_validate_report_tree(
            report_id=self._report.id_,
            offer_id=self._offer.offer_id,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        pass


class SvcInvalidateReportUseCase(SvcBTTriggerBase):
    """Emit RmInvalidateReportActivity (TentativeReject) for the given offer."""

    def _prepare(self) -> None:
        request = cast(InvalidateReportTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._offer, self._report = _resolve_offer_and_report(
            request.offer_id, self._dl
        )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return create_invalidate_report_trigger_tree(
            offer_id=self._offer.offer_id,
            report_id=self._report.id_,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' invalidated offer '%s' (report '%s')",
            self._actor_id,
            self._offer.offer_id,
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

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return create_reject_report_trigger_tree(
            offer_id=self._offer.offer_id,
            report_id=self._report.id_,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        request = cast(RejectReportTriggerRequest, self._request)
        logger.info(
            "Actor '%s' hard-closed offer '%s' (report '%s'); note: %s",
            self._actor_id,
            self._offer.offer_id,
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

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return create_close_report_trigger_tree(
            offer_id=self._offer.offer_id,
            report_id=self._report.id_,
            result_out=self._result_out,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        request = cast(CloseReportTriggerRequest, self._request)
        logger.info(
            "Actor '%s' closed offer '%s' (report '%s') via RM lifecycle;"
            " note: %s",
            self._actor_id,
            self._offer.offer_id,
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
