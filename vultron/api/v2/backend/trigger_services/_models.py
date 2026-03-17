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
Pydantic request models for trigger endpoints.

CS-09-002: ValidateReportRequest, InvalidateReportRequest, and
CloseReportRequest share a common base (ReportTriggerRequest) because they
have identical fields.  RejectReportRequest also uses offer_id but requires
a non-optional note field.
"""

import logging
import re
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_validator

logger = logging.getLogger(__name__)

_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*:[^\s]")


class ReportTriggerRequest(BaseModel):
    """
    Shared base for report-level trigger requests.

    TB-03-001: Must include offer_id to identify the target offer.
    TB-03-002: Unknown fields are silently ignored (extra="ignore").
    TB-03-003: Optional note field may be included.
    """

    model_config = ConfigDict(extra="ignore")

    offer_id: str
    note: str | None = None


class ValidateReportRequest(ReportTriggerRequest):
    """Request body for the validate-report trigger endpoint."""


class InvalidateReportRequest(ReportTriggerRequest):
    """Request body for the invalidate-report trigger endpoint."""


class CloseReportRequest(ReportTriggerRequest):
    """
    Request body for the close-report trigger endpoint.

    Distinction from reject-report: close-report closes a report after the
    RM lifecycle has proceeded (RM → C transition; emits RC message), while
    reject-report hard-rejects an incoming offer before validation completes.
    """


class RejectReportRequest(BaseModel):
    """
    Request body for the reject-report trigger endpoint.

    TB-03-001: Must include offer_id to identify the target offer.
    TB-03-002: Unknown fields are silently ignored (extra="ignore").
    TB-03-004: note is required (hard-close decisions warrant documented
        justification); an empty note emits a WARNING.
    """

    model_config = ConfigDict(extra="ignore")

    offer_id: str
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


class CaseTriggerRequest(BaseModel):
    """
    Request body for case-level trigger endpoints.

    TB-03-001: Must include case_id to identify the target case.
    TB-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    case_id: str

    @field_validator("case_id")
    @classmethod
    def case_id_must_be_uri(cls, v: str) -> str:
        if not _URI_SCHEME_RE.match(v):
            raise ValueError(
                "case_id must be a URI (e.g. urn:uuid:... or https://...)"
            )
        return v


class ProposeEmbargoRequest(BaseModel):
    """
    Request body for the propose-embargo trigger endpoint.

    TB-03-001: Must include case_id to identify the target case.
    TB-03-002: Unknown fields are silently ignored (extra="ignore").
    TB-03-003: Optional note field may be included.
    end_time is required and must be timezone-aware and in the future.
    """

    model_config = ConfigDict(extra="ignore")

    case_id: str
    note: str | None = None
    end_time: datetime

    @field_validator("case_id")
    @classmethod
    def case_id_must_be_uri(cls, v: str) -> str:
        if not _URI_SCHEME_RE.match(v):
            raise ValueError(
                "case_id must be a URI (e.g. urn:uuid:... or https://...)"
            )
        return v

    @field_validator("end_time")
    @classmethod
    def end_time_must_be_tz_aware_and_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("end_time must be timezone-aware")
        if v <= datetime.now(tz=timezone.utc):
            raise ValueError("end_time must be in the future")
        return v


class EvaluateEmbargoRequest(BaseModel):
    """
    Request body for the evaluate-embargo trigger endpoint.

    TB-03-001: Must include case_id to identify the target case.
    TB-03-002: Unknown fields are silently ignored (extra="ignore").
    Optional proposal_id identifies the specific EmProposeEmbargoActivity to accept;
    if omitted, the first pending proposal for the case is used.
    """

    model_config = ConfigDict(extra="ignore")

    case_id: str
    proposal_id: str | None = None

    @field_validator("case_id")
    @classmethod
    def case_id_must_be_uri(cls, v: str) -> str:
        if not _URI_SCHEME_RE.match(v):
            raise ValueError(
                "case_id must be a URI (e.g. urn:uuid:... or https://...)"
            )
        return v


class TerminateEmbargoRequest(BaseModel):
    """
    Request body for the terminate-embargo trigger endpoint.

    TB-03-001: Must include case_id to identify the target case.
    TB-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    case_id: str

    @field_validator("case_id")
    @classmethod
    def case_id_must_be_uri(cls, v: str) -> str:
        if not _URI_SCHEME_RE.match(v):
            raise ValueError(
                "case_id must be a URI (e.g. urn:uuid:... or https://...)"
            )
        return v
