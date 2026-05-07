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
"""Persisted mapping from a vulnerability report to its case replica."""

from __future__ import annotations

import urllib.parse
from typing import Literal

from pydantic import Field, model_validator

from vultron.core.models.base import UriString, VultronObject


class VultronReportCaseLink(VultronObject):
    """Track the case associated with a submitted vulnerability report."""

    type_: Literal["ReportCaseLink"] = Field(  # type: ignore[assignment]
        default="ReportCaseLink",
        validation_alias="type",
        serialization_alias="type",
    )
    report_id: UriString = Field(..., description="URI of the linked report")
    case_id: UriString | None = Field(
        default=None,
        description="URI of the linked case replica, once known",
    )
    trusted_case_creator_id: UriString | None = Field(
        default=None,
        description=(
            "URI of the actor that the reporter sent the original report offer "
            "to.  Set at submission time; validated against the bootstrap "
            "Create(VulnerabilityCase) sender (CBT-01-005, CBT-01-006)."
        ),
    )
    trusted_case_actor_id: UriString | None = Field(
        default=None,
        description=(
            "URI of the CaseActor trusted for this case after bootstrap "
            "validation.  Extracted from the CASE_ACTOR participant in the "
            "bootstrap snapshot; used to validate subsequent "
            "Announce(VulnerabilityCase) senders (CBT-01-006)."
        ),
    )

    @classmethod
    def build_id(cls, report_id: str) -> str:
        """Return the stable DataLayer ID for *report_id*."""
        slug = urllib.parse.quote(report_id, safe="")
        return f"report-case-link/{slug}"

    @model_validator(mode="after")
    def _set_id(self) -> "VultronReportCaseLink":
        """Compute ``id_`` deterministically from ``report_id``."""
        self.id_ = self.build_id(self.report_id)
        return self
