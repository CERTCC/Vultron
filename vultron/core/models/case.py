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

"""Domain representation of a vulnerability case."""

from datetime import datetime
from typing import Any

from pydantic import Field

from vultron.core.models.base import VultronObject
from vultron.core.models.case_event import VultronCaseEvent
from vultron.core.models.case_status import VultronCaseStatus
from vultron.core.models.participant import VultronParticipant


class VultronCase(VultronObject):
    """Domain representation of a vulnerability case.

    Mirrors the Vultron-specific fields of ``VulnerabilityCase``.  Cross-
    references to related objects are stored as ``str`` ID values, which are
    valid members of the corresponding wire-type union fields (e.g.
    ``VulnerabilityReportRef``, ``CaseParticipantRef``), ensuring DataLayer
    round-trip compatibility.

    ``as_type`` is ``"VulnerabilityCase"`` so that TinyDB stores this in the
    same table as wire-created cases and ``record_to_object`` can round-trip
    it via the wire vocabulary registry.
    """

    as_type: str = "VulnerabilityCase"
    summary: str | None = None
    content: str | None = None
    url: str | None = None
    context: Any | None = None
    attributed_to: Any | None = None
    published: datetime | None = None
    updated: datetime | None = None
    case_participants: list[str | VultronParticipant] = Field(
        default_factory=list
    )
    actor_participant_index: dict[str, str] = Field(default_factory=dict)
    vulnerability_reports: list[str] = Field(default_factory=list)
    case_statuses: list[str | VultronCaseStatus] = Field(
        default_factory=lambda: [VultronCaseStatus()]
    )
    notes: list[str] = Field(default_factory=list)
    active_embargo: str | None = None
    proposed_embargoes: list[str] = Field(default_factory=list)
    case_activity: list[str] = Field(default_factory=list)
    events: list[VultronCaseEvent] = Field(default_factory=list)
    parent_cases: list[str] = Field(default_factory=list)
    child_cases: list[str] = Field(default_factory=list)
    sibling_cases: list[str] = Field(default_factory=list)
