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


"""Request bodies for the report trigger verbs.

CS-09-002: ValidateReportRequest and InvalidateReportRequest share a common
base (ReportTriggerRequest) because they have identical fields.
RejectReportRequest also uses offer_id but requires a non-optional note field.
"""

import logging
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    JsonValue,
    field_validator,
    model_validator,
)

from vultron.core.models._helpers import (
    require_aware,
    timestamp_serializer,
)
from vultron.core.models.base import NonEmptyString, UriString

logger = logging.getLogger(__name__)


class ReportTriggerRequest(BaseModel):
    """
    Shared base for report-level trigger requests.

    TRIG-03-001: Must include offer_id to identify the target offer.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    TRIG-03-003: Optional note field may be included.
    """

    model_config = ConfigDict(extra="ignore")

    offer_id: NonEmptyString
    note: NonEmptyString | None = None


class AckReportRequest(ReportTriggerRequest):
    """Request body for the ack-report trigger endpoint."""


class ValidateReportRequest(ReportTriggerRequest):
    """Request body for the validate-report trigger endpoint."""


class InvalidateReportRequest(ReportTriggerRequest):
    """Request body for the invalidate-report trigger endpoint."""


class RejectReportRequest(BaseModel):
    """
    Request body for the reject-report trigger endpoint.

    TRIG-03-001: Must include offer_id to identify the target offer.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    TRIG-03-004: note is required (hard-close decisions warrant documented
        justification); an empty note emits a WARNING.
    """

    model_config = ConfigDict(extra="ignore")

    offer_id: NonEmptyString
    note: str

    @field_validator("note")
    @classmethod
    def note_must_be_present(cls, v: str) -> str:
        if not v.strip():
            logger.warning(
                "reject-report trigger received an empty note field; "
                "hard-close decisions should include a documented reason."
            )
        return v


def require_report_name_or_csaf(
    report_name: str | None, csaf_document: object | None
) -> None:
    """Refuse a submit-report request that leaves the report nameless.

    The name is optional only when a CSAF document comes with the request,
    whose ``document.title`` then fills it (CSAF-04-010).

    Raises:
        ValueError: neither ``report_name`` nor ``csaf_document`` is given.
    """
    if report_name is None and csaf_document is None:
        raise ValueError(
            "report_name is required unless a csaf_document supplies the"
            " report's name (CSAF-04-010)"
        )


class SubmitReportFields(BaseModel):
    """The submit-report fields the HTTP body and the core request share.

    ``report_name`` and ``report_summary`` name and summarize the report;
    ``report_content`` is its text, kept as the report's own ``content``
    whatever document comes with it (CSAF-01-001).  Each of
    ``report_name``, ``report_summary`` and ``proposed_embargo_end_time``
    that is stated wins over the value an attached CSAF document gives
    (CSAF-02-003, CSAF-04-010).  The CSAF document itself takes one form on
    the HTTP body (a JSON object) and another on the core request (the edge's
    reading of it), so each subclass declares its own ``csaf_document``.

    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    report_name: NonEmptyString | None = None
    report_content: NonEmptyString
    recipient_id: UriString
    #: The report's summary, the AS2 ``summary`` of the report.
    report_summary: NonEmptyString | None = None
    #: The Reporter's proposed embargo end for this report (EP-04-004).  When
    #: present the Offer carries a ``proposedEmbargo`` ending then; absent
    #: means no terms are stated and the receiver's default applies, unless
    #: an attached CSAF document gives a future disclosure date (CSAF-04-010).
    proposed_embargo_end_time: datetime | None = None
    _serialize_proposed_embargo_end_time = timestamp_serializer(
        "proposed_embargo_end_time"
    )

    @field_validator("proposed_embargo_end_time")
    @classmethod
    def proposed_end_must_be_tz_aware(
        cls, v: datetime | None
    ) -> datetime | None:
        # Whether it is in the future is the trigger's to judge, against its
        # act's instant (ADR-0176).
        return require_aware(v, "proposed_embargo_end_time")


class SubmitReportRequest(SubmitReportFields):
    """Request body for the submit-report trigger endpoint.

    The finder uses this to create a VulnerabilityReport and offer it to a
    recipient.  The actor_id is taken from the URL path; report_content and
    recipient_id must be supplied in the request body, and report_name too
    unless a csaf_document is.

    ``csaf_document`` is a CSAF 2.1 document, as a JSON object, to attach to
    the report.  The trigger refuses, with HTTP 422 naming each fault, one
    that fails the CSAF 2.1 schema, is not a ``csaf_vulnerability_report``,
    or is longer than a receiver reads (CSAF-04-009), and fills a report
    name, summary or proposed embargo end the request leaves out from it
    (CSAF-04-010).
    """

    csaf_document: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def _named_or_csaf(self) -> "SubmitReportRequest":
        require_report_name_or_csaf(self.report_name, self.csaf_document)
        return self
