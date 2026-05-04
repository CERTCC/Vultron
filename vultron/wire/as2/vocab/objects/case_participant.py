#!/usr/bin/env python
"""
Provides various CaseParticipant objects for the Vultron ActivityStreams Vocabulary.
"""

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from __future__ import annotations

import logging
from typing import TypeAlias, cast

from pydantic import Field, field_serializer, field_validator, model_validator

from vultron.core.models.participant import VultronParticipant
from vultron.core.states.rm import RM, is_valid_rm_transition
from vultron.core.states.roles import CVDRole, serialize_roles, validate_roles
from vultron.core.models.base import NonEmptyString
from vultron.core.models.enums import VultronObjectType as VO_type
from vultron.wire.as2.vocab.base.links import ActivityStreamRef, as_Link
from vultron.wire.as2.vocab.objects.base import (
    VultronAS2Object,
    _scalar_ref_id_or_value,
)
from vultron.wire.as2.vocab.objects.case_status import ParticipantStatus

logger = logging.getLogger(__name__)


class CaseParticipant(VultronAS2Object):
    """
    A CaseParticipant is a wrapper around an Actor in a VulnerabilityCase.
    It is used to track the status of the participant within the context of a specific case, as well as the roles they
    play in the case.

    Several subclasses of CaseParticipant are provided for convenience, including:

    - FinderParticipant
    - ReporterParticipant
    - FinderReporterParticipant
    - VendorParticipant
    - DeployerParticipant
    - CoordinatorParticipant
    - OtherParticipant

    But you can also create your own CaseParticipant objects if you need to.

    Examples:
        The following example creates a case participant and adds the VENDOR and DEPLOYER roles to it.

        ```python
        actor = as_Actor(name="Actor Name")
        cp = CaseParticipant(attributed_to=actor, context="case_id_foo")
        cp.add_role(CVDRole.VENDOR)
        cp.add_role(CVDRole.DEPLOYER)
        ```
    """

    type_: VO_type = Field(
        default=VO_type.CASE_PARTICIPANT,
        validation_alias="type",
        serialization_alias="type",
    )

    name: NonEmptyString | None = None
    case_roles: list[CVDRole] = Field(default_factory=list)
    participant_statuses: list[ParticipantStatus] = Field(default_factory=list)
    accepted_embargo_ids: list[str] = Field(default_factory=list)
    embargo_consent_state: str = Field(default="NO_EMBARGO")
    participant_case_name: NonEmptyString | None = Field(
        default=None, exclude=True
    )
    context: as_Link | str | None = Field(default=None, repr=True)

    @field_serializer("case_roles")
    def serialize_case_roles(self, value: list[CVDRole]) -> list[str]:
        return serialize_roles(value)

    @field_validator("case_roles", mode="before")
    @classmethod
    def validate_case_roles(cls, value: object) -> list[CVDRole]:
        return validate_roles(value)

    @model_validator(mode="after")
    def set_name_if_empty(self):
        """If name is empty, set it to the attributed_to's name if available, otherwise set it to the string representation of attributed_to."""
        if self.name is not None:
            # name is already set, do nothing
            return self

        if self.attributed_to is None:
            # attributed_to is not set, cannot set name
            return self

        if hasattr(self.attributed_to, "name"):
            self.name = self.attributed_to.name
        else:
            self.name = str(self.attributed_to)

        return self

    @model_validator(mode="after")
    def init_participant_status_if_empty(self):
        if self.participant_statuses:
            # participant status is already set, do nothing
            return self

        # participant status is empty, so initialize it with a default status
        self.participant_statuses = [
            ParticipantStatus(
                context=self.context or self.id_,
                attributed_to=self.attributed_to,
            ),
        ]
        return self

    @property
    def participant_status(self) -> ParticipantStatus | None:
        """Return the most recent ParticipantStatus (read-only; see participant_statuses for history)."""
        if not self.participant_statuses:
            return None
        return max(
            self.participant_statuses,
            key=lambda ps: ps.updated or ps.published or ps.id_,
        )

    def append_rm_state(self, rm_state: RM, actor: str, context: str) -> bool:
        """Append a new ParticipantStatus with the given RM state.

        Skips the append (with a WARNING) if the transition from the current
        RM state to rm_state is not valid according to the RM state machine.

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
            ParticipantStatus(
                attributed_to=actor,
                context=context,
                rm_state=rm_state,
            )
        )
        return True

    def add_role(
        self, role: CVDRole, raise_when_present: bool = False
    ) -> None:
        """Add a role to the participant.

        Idempotent when role already exists. Raises ``KeyError`` when
        ``raise_when_present=True`` and the role is already present.

        Args:
            role: CVD role to add.
            raise_when_present: when True, raise KeyError if role already held.

        Raises:
            KeyError: when raise_when_present is True and role already present.
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
        """Remove a role from the participant.

        Idempotent when role does not exist. Raises ``KeyError`` when
        ``raise_when_missing=True`` and the role is not held.

        Args:
            role: CVD role to remove.
            raise_when_missing: when True, raise KeyError if role not present.

        Raises:
            KeyError: when raise_when_missing is True and role not present.
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
        """Return True when the participant holds the given role."""
        return role in self.case_roles

    @property
    def roles(self) -> list[CVDRole]:
        """Return the participant's current CVD roles (read-only copy)."""
        return list(self.case_roles)

    @classmethod
    def from_core(cls, core_obj: VultronParticipant) -> "CaseParticipant":
        return cast("CaseParticipant", super().from_core(core_obj))

    def to_core(self) -> VultronParticipant:
        data = self._to_core_data()
        data["attributed_to"] = _scalar_ref_id_or_value(
            data.get("attributed_to")
        )
        data["context"] = _scalar_ref_id_or_value(data.get("context"))
        data["participant_statuses"] = [
            (
                status.to_core()
                if isinstance(status, ParticipantStatus)
                else status
            )
            for status in self.participant_statuses
        ]
        return VultronParticipant.model_validate(data)


class FinderParticipant(CaseParticipant):
    """
    A FinderParticipant is a CaseParticipant that has the FINDER role in a VulnerabilityCase.
    """

    @model_validator(mode="after")
    def set_role(self):
        """Set the FINDER role."""
        self.case_roles = []
        self.add_role(CVDRole.FINDER)
        return self


class ReporterParticipant(CaseParticipant):
    """
    A ReporterParticipant is a CaseParticipant that has the REPORTER role in a VulnerabilityCase.
    """

    @model_validator(mode="after")
    def set_role(self):
        """Set the REPORTER role."""
        self.case_roles = []
        self.add_role(CVDRole.REPORTER)
        return self

    @model_validator(mode="after")
    def set_accepted_status(self):
        # by definition, to be a reporter, you must have accepted the report
        pstatus = ParticipantStatus(
            context=self.context or self.id_,
            attributed_to=self.attributed_to,
            rm_state=RM.ACCEPTED,
        )
        self.participant_statuses = [pstatus]

        return self


class FinderReporterParticipant(CaseParticipant):
    """
    A FinderReporterParticipant is a CaseParticipant that has both the FINDER and REPORTER roles in a
    VulnerabilityCase.
    """

    @model_validator(mode="after")
    def set_roles(self) -> FinderReporterParticipant:
        """Set both FINDER and REPORTER roles."""
        self.case_roles = []
        self.add_role(CVDRole.FINDER)
        self.add_role(CVDRole.REPORTER)
        return self

    @model_validator(mode="after")
    def set_accepted_status(self) -> FinderReporterParticipant:
        """
        Set the participant status to ACCEPTED, since by definition,
        to be a reporter, you must have accepted the report
        """
        pstatus = ParticipantStatus(
            context=self.context or self.id_,
            attributed_to=self.attributed_to,
            rm_state=RM.ACCEPTED,
        )
        self.participant_statuses = [pstatus]

        return self


class VendorParticipant(CaseParticipant):
    """
    A VendorParticipant is a CaseParticipant that has the VENDOR role in a VulnerabilityCase.
    """

    @model_validator(mode="after")
    def set_role(self):
        """Set the VENDOR role."""
        self.case_roles = []
        self.add_role(CVDRole.VENDOR)
        return self


class DeployerParticipant(CaseParticipant):
    """
    A DeployerParticipant is a CaseParticipant that has the DEPLOYER role in a VulnerabilityCase.
    """

    @model_validator(mode="after")
    def set_role(self) -> DeployerParticipant:
        """Set the DEPLOYER role."""
        self.case_roles = []
        self.add_role(CVDRole.DEPLOYER)
        return self


class CoordinatorParticipant(CaseParticipant):
    """
    A CoordinatorParticipant is a CaseParticipant that has the COORDINATOR role in a VulnerabilityCase.
    """

    @model_validator(mode="after")
    def set_role(self):
        """Set the COORDINATOR role."""
        self.case_roles = []
        self.add_role(CVDRole.COORDINATOR)
        return self


class OtherParticipant(CaseParticipant):
    """
    An OtherParticipant is a CaseParticipant that has the OTHER role in a VulnerabilityCase.
    """

    @model_validator(mode="after")
    def set_role(self):
        """Set the OTHER role."""
        self.case_roles = []
        self.add_role(CVDRole.OTHER)
        return self


CaseParticipantRef: TypeAlias = ActivityStreamRef[
    CaseParticipant
    | FinderParticipant
    | ReporterParticipant
    | VendorParticipant
    | DeployerParticipant
    | CoordinatorParticipant
    | OtherParticipant
]


def main():
    from vultron.wire.as2.vocab.base.objects.actors import as_Actor

    actor = as_Actor(name="Actor Name")
    cp = CaseParticipant(attributed_to=actor, context="case_id_foo")
    print(f"### {cp.type_} ###")
    print()
    print(cp.to_json(indent=2))
    print()
    print()

    for role in [
        FinderParticipant,
        ReporterParticipant,
        VendorParticipant,
        DeployerParticipant,
        CoordinatorParticipant,
        OtherParticipant,
    ]:
        obj = role(
            attributed_to=actor, context="https://for.example/case/99999"
        )
        print(f"### {obj.type_} ###")
        print()
        print(obj.to_json(indent=2))
        print()
        print()


if __name__ == "__main__":
    main()
