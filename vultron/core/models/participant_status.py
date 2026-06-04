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

"""Domain representation of a participant RM-state status record."""

from typing import Literal

from pydantic import Field, field_serializer, field_validator

from vultron.core.states.rm import RM
from vultron.core.states.cs import CS_vfd
from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.case_status import CaseStatus


class ParticipantStatus(CoreObject):
    """Domain representation of a participant RM-state status record.

    Canonical core type for the Vultron ``ParticipantStatus`` object.
    ``type_`` is ``"ParticipantStatus"`` to match the wire value and
    to auto-register this class in :data:`CORE_VOCABULARY`.

    ``context`` (case ID) is required — a participant status is always
    associated with a specific case.

    ``case_status`` embeds the participant's perspective on the case-level
    state (em_state and pxa_state) via a nested :class:`CaseStatus` object.
    """

    type_: Literal["ParticipantStatus"] = Field(
        default="ParticipantStatus",
        validation_alias="type",
        serialization_alias="type",
    )
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
    rm_state: RM = RM.START
    vfd_state: CS_vfd = CS_vfd.vfd
    case_engagement: bool = True
    embargo_adherence: bool = True
    tracking_id: NonEmptyString | None = None
    case_status: CaseStatus | None = None

    @field_serializer("rm_state")
    def _serialize_rm_state(self, v: RM) -> str:
        return v.name

    @field_serializer("vfd_state")
    def _serialize_vfd_state(self, v: CS_vfd) -> str:
        return v.name

    @field_validator("rm_state", mode="before")
    @classmethod
    def _validate_rm_state(cls, v: object) -> RM:
        if isinstance(v, str):
            return RM[v]
        return v  # type: ignore[return-value]

    @field_validator("vfd_state", mode="before")
    @classmethod
    def _validate_vfd_state(cls, v: object) -> CS_vfd:
        if isinstance(v, str):
            return CS_vfd[v]
        return v  # type: ignore[return-value]
