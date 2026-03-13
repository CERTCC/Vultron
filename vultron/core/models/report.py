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

"""Domain representation of a vulnerability report."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from vultron.core.models._helpers import _new_urn


class VultronReport(BaseModel):
    """Domain representation of a vulnerability report.

    Mirrors the Vultron-specific fields of ``VulnerabilityReport``.
    Policy implementations receive this type when evaluating credibility and
    validity.
    ``as_type`` is ``"VulnerabilityReport"`` to match the wire value.
    """

    as_id: str = Field(default_factory=_new_urn)
    as_type: str = "VulnerabilityReport"
    name: str | None = None
    summary: str | None = None
    content: Any | None = None
    url: str | None = None
    media_type: str | None = None
    attributed_to: Any | None = None
    context: Any | None = None
    published: datetime | None = None
    updated: datetime | None = None
