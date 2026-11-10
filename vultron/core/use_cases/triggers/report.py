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
from datetime import datetime
from typing import Any, cast

import py_trees.behaviour

from vultron.core.behaviors.report.trigger_report_trees import (
    create_ack_report_trigger_tree,
    create_invalidate_report_trigger_tree,
    create_reject_report_trigger_tree,
    submit_report_trigger_bt,
)
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_tree,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.use_case_result import OfferResult
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.predicates.addressing import is_addressed_to
from vultron.core.services.report_case_inputs import (
    StatedReportFields,
    case_inputs_from_claims,
)
from vultron.core.services.submitted_csaf import submitted_csaf_violations
from vultron.core.use_cases.triggers._base import (
    SvcActivityTriggerBase,
    SvcBTTriggerBase,
)
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
)
from vultron.core.use_cases.triggers.requests import (
    AckReportTriggerRequest,
    InvalidateReportTriggerRequest,
    RejectReportTriggerRequest,
    SubmitReportTriggerRequest,
    ValidateReportTriggerRequest,
)
from vultron.errors import (
    VultronAlreadyExistsError,
    VultronNotFoundError,
    VultronValidationError,
)

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


def _require_offer_addressed_to(
    actor_id: str, offer_record: VultronOfferRecord, trigger: str
) -> None:
    """Refuse *trigger* unless *actor_id* received the Offer (CM-11-020).

    Only a ``to`` recipient of the ``Offer(VulnerabilityReport)`` answers it
    (HP-09-001).  A participant that joined through an Invite never received
    that Offer, so the record's ``offer_to`` does not name it; it judges the
    case by replying to the full-case Invite (CM-11-011, ADR-0121).
    """
    if not is_addressed_to(actor_id, offer_record.offer_to):
        raise VultronValidationError(
            f"{trigger} refused: actor '{actor_id}' was not sent offer "
            f"'{offer_record.offer_id}'. A participant that joined the case "
            "through an Invite judges the case by replying to the full-case "
            "Invite, not by answering the original report Offer (CM-11-020)."
        )


class SvcAckReportUseCase(SvcActivityTriggerBase):
    """Acknowledge a report Offer by emitting RK to the reporter.

    RK goes from an actor the ``Offer(VulnerabilityReport)`` was addressed to,
    to the reporter, at any time after the report arrived, whether or not a
    case exists: it answers the reporter's Offer outside the case, so it is
    the stated exception to PCR-08-001.  Nobody sends it to the CASE_MANAGER
    (RMB-08-005).  An actor the Offer was not sent to is refused before
    anything is emitted.
    """

    def _prepare(self) -> None:
        request = cast(AckReportTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._offer, self._report = _resolve_offer_and_report(
            request.offer_id, self._dl
        )
        _require_offer_addressed_to(self._actor_id, self._offer, "ack-report")

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        request = cast(AckReportTriggerRequest, self._request)
        return create_ack_report_trigger_tree(
            offer_id=self._offer.offer_id,
            report_id=self._report.id_,
            note=request.note,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        request = cast(AckReportTriggerRequest, self._request)
        logger.info(
            "Actor '%s' acknowledged offer '%s' (report '%s'); note: %s",
            self._actor_id,
            self._offer.offer_id,
            self._report.id_,
            request.note,
        )


class SvcValidateReportUseCase(SvcActivityTriggerBase):
    """Validate a report offer using the ValidateReportBT behavior tree.

    Per ADR-0021 CLP-10-027: the validate trigger tree now emits an
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
        _require_offer_addressed_to(
            self._actor_id, self._offer, "validate-report"
        )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return create_validate_report_tree(
            report_id=self._report.id_,
            offer_id=self._offer.offer_id,
            captured=self._captured,
            sender_actor_id=self._actor_id,
        )

    def _handle_result(self) -> None:
        pass


class SvcInvalidateReportUseCase(SvcActivityTriggerBase):
    """Emit RmInvalidateReportActivity (TentativeReject) for the given offer."""

    def _prepare(self) -> None:
        request = cast(InvalidateReportTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._offer, self._report = _resolve_offer_and_report(
            request.offer_id, self._dl
        )
        _require_offer_addressed_to(
            self._actor_id, self._offer, "invalidate-report"
        )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return create_invalidate_report_trigger_tree(
            offer_id=self._offer.offer_id,
            report_id=self._report.id_,
            captured=self._captured,
            sender_actor_id=self._actor_id,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' invalidated offer '%s' (report '%s')",
            self._actor_id,
            self._offer.offer_id,
            self._report.id_,
        )


class SvcRejectReportUseCase(SvcActivityTriggerBase):
    """Hard-close a report offer by emitting RmCloseReportActivity (Reject)."""

    def _prepare(self) -> None:
        request = cast(RejectReportTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._offer, self._report = _resolve_offer_and_report(
            request.offer_id, self._dl
        )
        _require_offer_addressed_to(
            self._actor_id, self._offer, "reject-report"
        )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return create_reject_report_trigger_tree(
            offer_id=self._offer.offer_id,
            report_id=self._report.id_,
            captured=self._captured,
            sender_actor_id=self._actor_id,
            result_out=self._result_out,
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


class SvcSubmitReportUseCase(SvcBTTriggerBase[OfferResult]):
    """Create a VulnerabilityReport and offer it to a recipient.

    Stores the report and a VultronReportCaseLink in the actor's DataLayer
    during ``_prepare()``, then runs ``SubmitReportTriggerBT`` to build
    and queue the Offer activity.  Returns ``{"offer": <offer_dict>}``
    rather than the base-class ``{"activity": ...}`` shape to preserve
    the existing API contract.

    When the request states ``proposed_embargo_end_time``, ``_prepare()``
    also stores the Reporter's proposed ``EmbargoEvent`` — about the report,
    since no case exists yet (EP-04-009) — and the tree carries it on the
    Offer as ``proposedEmbargo`` (EP-04-004).  The Reporter keeps the event
    under the id the Offer names: the CASE_MANAGER keeps that identity when
    the terms win, so the Reporter can recognise its own terms on the case.

    When the request carries a CSAF document, ``_prepare()`` refuses it,
    before anything is stored or sent, when it fails the CSAF 2.1 schema or
    is not a ``csaf_vulnerability_report`` (CSAF-04-009, CSAF-02-007).  A
    document it takes is attached to the report as a ``Document``
    (CSAF-01-001, CSAF-01-002) and fills the report name, summary and
    proposed embargo end the request leaves out, by the CSAF-03 mapping
    measured against this act's instant (CSAF-04-010, CSAF-02-004).
    """

    def _prepare(self) -> None:
        request = cast(SubmitReportTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_

        fields = self._report_fields(request)
        report = VulnerabilityReport(
            name=fields.name,
            summary=fields.summary,
            content=request.report_content,
            attributed_to=self._actor_id,
            attachment=(
                [request.csaf_document.attachment]
                if request.csaf_document is not None
                else None
            ),
        )
        try:
            self._dl.create(report)
        except VultronAlreadyExistsError:
            logger.warning(
                "VulnerabilityReport '%s' already exists", report.id_
            )

        logger.info(
            "Created VulnerabilityReport '%s' (id: '%s')",
            report.name,
            report.id_,
        )

        try:
            self._dl.create(
                VultronReportCaseLink(
                    report_id=report.id_,
                    case_creator_id=request.recipient_id,
                )
            )
        except VultronAlreadyExistsError:
            logger.debug(
                "SvcSubmitReportUseCase: ReportCaseLink for '%s' already "
                "exists — preserving existing link (idempotent)",
                report.id_,
            )

        self._report_id = report.id_
        self._recipient_id = request.recipient_id
        self._proposed_embargo_id = self._store_proposed_embargo(
            report, fields.proposed_embargo_end
        )

    def _report_fields(
        self, request: SubmitReportTriggerRequest
    ) -> StatedReportFields:
        """The report's name, summary and proposed embargo end.

        Each one the request states; one it leaves out, from the attached
        CSAF document by the CSAF-03 mapping, measured against this act's
        instant (CSAF-04-010).  A stated embargo end is kept even when the
        document sets P, X or A, for which the mapping proposes none: the
        Reporter's terms are its to state, and the receiver decides
        (EP-04-020).

        Raises:
            VultronValidationError: the CSAF document has a fault that keeps
                it off the report (CSAF-04-009), each one named.
        """
        stated = StatedReportFields(
            name=request.report_name,
            summary=request.report_summary,
            proposed_embargo_end=request.proposed_embargo_end_time,
        )
        submission = request.csaf_document
        if submission is None:
            return stated
        violations = submitted_csaf_violations(submission)
        if violations:
            raise VultronValidationError(
                f"submit-report refuses the CSAF document of actor"
                f" '{self._actor_id}': it has {len(violations)} fault(s)"
                " (CSAF-04-009)",
                violations=violations,
            )
        filled = case_inputs_from_claims(
            submission.reading.claims, reference_time=self._at, stated=stated
        )
        fields = StatedReportFields(
            name=filled.name,
            summary=filled.summary,
            proposed_embargo_end=stated.proposed_embargo_end
            or filled.proposed_embargo_end,
        )
        filled_names = [
            name
            for name in ("name", "summary", "proposed_embargo_end")
            if getattr(stated, name) is None
            and getattr(fields, name) is not None
        ]
        if filled_names:
            logger.info(
                "Actor '%s' fills report %s from CSAF document '%s'"
                " (CSAF-04-010)",
                self._actor_id,
                ", ".join(filled_names),
                submission.attachment.id_,
            )
        return fields

    def _store_proposed_embargo(
        self,
        report: VulnerabilityReport,
        end_time: datetime | None,
    ) -> str | None:
        """Persist the Reporter's proposed terms for *report*, if any stated.

        Returns the stored ``EmbargoEvent`` id, or ``None`` when the request
        proposes nothing.  The event names the report as its ``context``
        (EP-04-009); the case does not exist yet.
        """
        if end_time is None:
            return None
        proposal = EmbargoEvent(
            context=report.id_,
            end_time=end_time,
        )
        self._dl.create(proposal)
        logger.info(
            "Reporter '%s' proposes embargo '%s' ending %s for report '%s'"
            " (EP-04-004)",
            self._actor_id,
            proposal.id_,
            proposal.end_time.isoformat(),
            report.id_,
        )
        return proposal.id_

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return submit_report_trigger_bt(
            report_id=self._report_id,
            recipient_id=self._recipient_id,
            captured=self._captured,
            proposed_embargo_id=self._proposed_embargo_id,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Offering report '%s' to '%s'",
            self._report_id,
            self._recipient_id,
        )

    def _build_result(self) -> OfferResult:
        """The body is the captured ``Offer(VulnerabilityReport)`` alone."""
        return OfferResult(offer=self._captured.get("offer"))
