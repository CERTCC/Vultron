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

from typing import Literal

from pydantic import Field, model_validator

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

    When first created with an ``attributed_to`` actor and an empty
    ``case_statuses`` list, an initial ``VultronCaseStatus`` is appended
    automatically so that ``current_status`` (on the wire
    ``VulnerabilityCase``) never encounters an empty history list.
    """

    as_type: Literal["VulnerabilityCase"] = "VulnerabilityCase"
    case_participants: list[str | VultronParticipant] = Field(
        default_factory=list
    )
    actor_participant_index: dict[str, str] = Field(default_factory=dict)
    vulnerability_reports: list[str] = Field(default_factory=list)
    case_statuses: list[str | VultronCaseStatus] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    active_embargo: str | None = None
    proposed_embargoes: list[str] = Field(default_factory=list)
    case_activity: list[str] = Field(default_factory=list)
    events: list[VultronCaseEvent] = Field(default_factory=list)
    parent_cases: list[str] = Field(default_factory=list)
    child_cases: list[str] = Field(default_factory=list)
    sibling_cases: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def init_case_statuses(self) -> "VultronCase":
        if not self.case_statuses and self.attributed_to:
            self.case_statuses = [
                VultronCaseStatus(
                    context=self.as_id,
                    attributed_to=self.attributed_to,
                )
            ]
        return self
