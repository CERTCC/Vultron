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

"""Core trigger requests for the report verbs."""

from pydantic import model_validator

from vultron.core.models.base import NonEmptyString
from vultron.core.models.report_claims import SubmittedCsafDocument
from vultron.core.models.use_case_result import (
    ActivityResult,
    OfferResult,
)
from vultron.core.use_cases.triggers.request_bodies import (
    AckReportRequest,
    InvalidateReportRequest,
    ReportTriggerRequest,
    SubmitReportFields,
    ValidateReportRequest,
    require_report_name_or_csaf,
)
from vultron.core.use_cases.triggers.requests._base import TriggerRequest


class OfferTriggerRequest(
    TriggerRequest[ActivityResult], ReportTriggerRequest
):
    """Trigger request that requires an ``offer_id``."""


class AckReportTriggerRequest(OfferTriggerRequest, AckReportRequest):
    pass


class ValidateReportTriggerRequest(OfferTriggerRequest, ValidateReportRequest):
    pass


class InvalidateReportTriggerRequest(
    OfferTriggerRequest, InvalidateReportRequest
):
    pass


class RejectReportTriggerRequest(OfferTriggerRequest):
    """Requires ``offer_id``; ``note`` is strongly encouraged but coerced to
    ``None`` (not rejected) when the caller supplies an empty string, since
    the HTTP adapter already logs a warning in that case.

    Deliberately not derived from ``RejectReportRequest``: that body requires
    the ``note`` key so a client must state a reason (TRIG-03-004), while the
    core request accepts the coerced ``None`` the route passes through.
    """

    note: NonEmptyString | None = None


class SubmitReportTriggerRequest(
    TriggerRequest[OfferResult], SubmitReportFields
):
    """Trigger request for a finder to create and offer a vulnerability report.

    Creates a ``VulnerabilityReport`` in the actor's DataLayer and queues an
    ``RmSubmitReportActivity`` offer to the specified recipient.

    ``csaf_document`` is the edge's reading of the CSAF document the body
    carried (``vultron.wire.csaf.reader.read_submitted_csaf_document``), so
    core judges and reads it without importing wire (ARCH-01-001, ADR-0032).
    Deliberately not derived from ``SubmitReportRequest``, whose
    ``csaf_document`` is the raw JSON object.
    """

    csaf_document: SubmittedCsafDocument | None = None

    @model_validator(mode="after")
    def _named_or_csaf(self) -> SubmitReportTriggerRequest:
        require_report_name_or_csaf(self.report_name, self.csaf_document)
        return self
