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

from pydantic import BaseModel, ConfigDict, field_validator

from vultron.core.models._helpers import (
    require_future_aware,
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


class SubmitReportRequest(BaseModel):
    """Request body for the submit-report trigger endpoint.

    The finder uses this to create a VulnerabilityReport and offer it to a
    recipient.  The actor_id is taken from the URL path; report_name,
    report_content, and recipient_id must be supplied in the request body.

    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    report_name: NonEmptyString
    report_content: NonEmptyString
    recipient_id: UriString
    #: The Reporter's proposed embargo end for this report (EP-04-004).  When
    #: present the Offer carries a ``proposedEmbargo`` ending then; absent
    #: means no terms are stated and the receiver's default applies.
    proposed_embargo_end_time: datetime | None = None
    _serialize_proposed_embargo_end_time = timestamp_serializer(
        "proposed_embargo_end_time"
    )

    @field_validator("proposed_embargo_end_time")
    @classmethod
    def proposed_end_must_be_tz_aware_and_future(
        cls, v: datetime | None
    ) -> datetime | None:
        return require_future_aware(v, "proposed_embargo_end_time")
