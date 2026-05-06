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
