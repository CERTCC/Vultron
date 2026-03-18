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

"""Domain representation of a case participant."""

from typing import Any

from pydantic import Field, field_serializer, field_validator

from vultron.bt.roles.states import CVDRoles
from vultron.core.models.base import VultronObject
from vultron.core.models.participant_status import VultronParticipantStatus


class VultronParticipant(VultronObject):
    """Domain representation of a case participant.

    Mirrors the Vultron-specific fields of ``CaseParticipant`` and its
    subclasses (VendorParticipant, etc.).
    ``as_type`` is ``"CaseParticipant"`` to match the wire value shared by all
    ``CaseParticipant`` subclasses.
    """

    as_type: str = "CaseParticipant"
    attributed_to: Any | None = None
    context: str | None = None
    case_roles: list[CVDRoles] = Field(default_factory=list)
    participant_statuses: list[VultronParticipantStatus] = Field(
        default_factory=list
    )
    accepted_embargo_ids: list[str] = Field(default_factory=list)
    participant_case_name: str | None = None

    @field_serializer("case_roles")
    def _serialize_case_roles(self, value: list[CVDRoles]) -> list[str]:
        return [role.name for role in value]

    @field_validator("case_roles", mode="before")
    @classmethod
    def _validate_case_roles(cls, value: list) -> list:
        if isinstance(value, list) and value and isinstance(value[0], str):
            return [CVDRoles[name] for name in value]
        return value
