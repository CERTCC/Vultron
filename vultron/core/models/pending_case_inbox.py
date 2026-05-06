#!/usr/bin/env python
"""Persisted queue of deferred case-scoped inbox activities."""

from __future__ import annotations

import urllib.parse
from typing import Literal

from pydantic import Field, model_validator

from vultron.core.models.base import UriString, VultronObject


class VultronPendingCaseInbox(VultronObject):
    """Store deferred inbox activity IDs keyed by case ID."""

    type_: Literal["PendingCaseInbox"] = Field(  # type: ignore[assignment]
        default="PendingCaseInbox",
        validation_alias="type",
        serialization_alias="type",
    )
    case_id: UriString = Field(..., description="URI of the pending case")
    activity_ids: list[UriString] = Field(
        default_factory=list,
        description="Deferred inbox activity IDs awaiting the case replica",
    )

    @classmethod
    def build_id(cls, case_id: str) -> str:
        """Return the stable DataLayer ID for *case_id*."""
        slug = urllib.parse.quote(case_id, safe="")
        return f"pending-case-inbox/{slug}"

    @model_validator(mode="after")
    def _set_id(self) -> "VultronPendingCaseInbox":
        """Compute ``id_`` deterministically from ``case_id``."""
        self.id_ = self.build_id(self.case_id)
        return self
