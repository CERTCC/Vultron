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

from pydantic import field_serializer

from vultron.core.states.rm import RM
from vultron.core.states.cs import CS_vfd
from vultron.core.models.base import NonEmptyString, VultronObject


class VultronParticipantStatus(VultronObject):
    """Domain representation of a participant RM-state status record.

    Mirrors the Vultron-specific fields of ``ParticipantStatus``.
    ``as_type`` is ``"ParticipantStatus"`` to match the wire value.

    ``context`` (case ID) is required, matching the wire type's constraint.
    """

    as_type: Literal["ParticipantStatus"] = "ParticipantStatus"
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
    rm_state: RM = RM.START
    vfd_state: CS_vfd = CS_vfd.vfd
    case_engagement: bool = True
    embargo_adherence: bool = True
    tracking_id: NonEmptyString | None = None
    case_status: NonEmptyString | None = None

    @field_serializer("vfd_state")
    def _serialize_vfd_state(self, v: CS_vfd) -> str:
        return v.name
