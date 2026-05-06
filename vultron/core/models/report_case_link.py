#!/usr/bin/env python
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
