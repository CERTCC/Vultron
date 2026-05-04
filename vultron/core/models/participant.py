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

from vultron.core.models.base import NonEmptyString, VultronObject
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM, is_valid_rm_transition
from vultron.core.states.roles import CVDRole, serialize_roles, validate_roles

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
    case_roles: list[CVDRole] = Field(default_factory=list)
    participant_statuses: list[VultronParticipantStatus] = Field(
        default_factory=list
    )
    accepted_embargo_ids: list[NonEmptyString] = Field(default_factory=list)
    embargo_consent_state: PEC = Field(default=PEC.NO_EMBARGO)
    participant_case_name: NonEmptyString | None = None

    @field_serializer("case_roles")
    def _serialize_case_roles(self, value: list[CVDRole]) -> list[str]:
        return serialize_roles(value)

    @field_validator("case_roles", mode="before")
    @classmethod
    def _validate_case_roles(cls, value: object) -> list[CVDRole]:
        return validate_roles(value)

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

    def add_role(
        self, role: CVDRole, raise_when_present: bool = False
    ) -> None:
        """
        Add a new role to the participant.
        Idempotent when role already exists in the participant.

        Args:
            role (CVDRole): New role to add.
            raise_when_present (bool): when true, raise a KeyError if the role already exists.

        Raises:
            KeyError: when raise_when_present is true and the role already exists in the participant.
        """
        roles = set(self.case_roles)

        if role not in roles:
            roles.add(role)
        else:
            logger.info(
                "Attempted to add role %s to participant %s, but role was already present",
                role,
                self,
            )
            if raise_when_present:
                raise KeyError(
                    f"Role {role} was already present in participant.case_roles"
                )

        self.case_roles = list(roles)

    def remove_role(
        self, role: CVDRole, raise_when_missing: bool = False
    ) -> None:
        """
        Remove a role from the participant.
        Idempotent when role does not exist in the participant.

        Args:
            role (CVDRole): New role to remove.
            raise_when_missing (bool): when true, raise a KeyError if the role does not exist in the participant.

        Raises:
            KeyError: when raise_when_missing is true and the role does not exist in the participant.
        """
        roles = set(self.case_roles)

        if role in roles:
            roles.remove(role)
        else:
            logger.info(
                "Attempted to remove role %s from participant %s, but role was not present",
                role,
                self,
            )
            if raise_when_missing:
                raise KeyError(
                    f"Role {role} was not present to delete from participant.case_roles"
                )

        self.case_roles = list(roles)

    def has_role(self, role: CVDRole) -> bool:
        """Return true when the participant has the given role."""
        return role in self.case_roles
