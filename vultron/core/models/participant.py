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

import logging

from pydantic import Field, field_serializer, field_validator

from vultron.core.states.rm import RM, is_valid_rm_transition
from vultron.core.states.roles import CVDRoles
from vultron.core.models.base import NonEmptyString, VultronObject
from vultron.core.models.participant_status import VultronParticipantStatus

logger = logging.getLogger(__name__)


class VultronParticipant(VultronObject):
    """Domain representation of a case participant.

    Mirrors the Vultron-specific fields of ``CaseParticipant`` and its
    subclasses (VendorParticipant, etc.).
    ``type_`` is ``"CaseParticipant"`` to match the wire value shared by all
    ``CaseParticipant`` subclasses.
    """

    type_: str = Field(
        default="CaseParticipant",
        validation_alias="type",
        serialization_alias="type",
    )
    attributed_to: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
    case_roles: list[CVDRoles] = Field(default_factory=list)
    participant_statuses: list[VultronParticipantStatus] = Field(
        default_factory=list
    )
    accepted_embargo_ids: list[NonEmptyString] = Field(default_factory=list)
    participant_case_name: NonEmptyString | None = None

    @field_serializer("case_roles")
    def _serialize_case_roles(self, value: list[CVDRoles]) -> list[str]:
        return [
            role.name if role.name is not None else str(role) for role in value
        ]

    @field_validator("case_roles", mode="before")
    @classmethod
    def _validate_case_roles(cls, value: list) -> list:
        if isinstance(value, list) and value and isinstance(value[0], str):
            return [CVDRoles[name] for name in value]
        return value

    def append_rm_state(self, rm_state: RM, actor: str, context: str) -> bool:
        """Append a new VultronParticipantStatus with the given RM state.

        Validates the transition against the RM state machine.
        Returns True when the status was appended, False when blocked.
        """
        current = (
            self.participant_statuses[-1].rm_state
            if self.participant_statuses
            else RM.START
        )
        if not is_valid_rm_transition(current, rm_state):
            logger.warning(
                "Invalid RM transition %s → %s for participant %s; skipping",
                current,
                rm_state,
                self.id_,
            )
            return False
        self.participant_statuses.append(
            VultronParticipantStatus(
                rm_state=rm_state,
                context=context,
                attributed_to=actor,
            )
        )
        return True
