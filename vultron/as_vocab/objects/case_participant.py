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

from typing import Literal

from pydantic import Field, field_validator, field_serializer, model_validator

from vultron.as_vocab.base import activitystreams_object
from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.base import VultronObject
from vultron.as_vocab.objects.case_status import ParticipantStatus
from vultron.bt.report_management.states import RM
from vultron.bt.roles.states import CVDRoles as CVDRole


@activitystreams_object
class CaseParticipant(VultronObject):
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
        cp = CaseParticipant(actor=actor, context="case_id_foo")
        cp.add_role(CVDRole.VENDOR)
        cp.add_role(CVDRole.DEPLOYER)
        ```
    """

    as_type: Literal["CaseParticipant"] = "CaseParticipant"

    actor: as_Actor | as_Link | str
    name: str | None = None
    case_roles: list[CVDRole] = Field(default_factory=list)
    participant_status: list[ParticipantStatus] = Field(default_factory=list)
    participant_case_name: str | None = Field(default=None, exclude=True)
    context: as_Link | str | None = Field(default=None, repr=True)

    @field_serializer("case_roles")
    def serialize_case_roles(self, value: list[CVDRole]) -> list[str]:
        return [role.name for role in value]

    @field_validator("case_roles", mode="before")
    @classmethod
    def validate_case_roles(cls, value):
        if isinstance(value, list) and value and isinstance(value[0], str):
            return [CVDRole[name] for name in value]
        return value

    @model_validator(mode="after")
    def post_init_setup(self):
        if len(self.case_roles) == 0:
            self.case_roles.append(CVDRole.NO_ROLE)

        if self.name is None:
            if self.actor is not None:
                if hasattr(self.actor, "name"):
                    self.name = self.actor.name
                else:
                    self.name = str(self.actor)

        if len(self.participant_status) == 0:
            self.participant_status.append(
                ParticipantStatus(
                    context=self.context,
                    actor=self.actor,
                )
            )

        return self

    def add_role(self, role: CVDRole, reset=False):
        if reset:
            self.case_roles = []
        self.case_roles.append(role)


@activitystreams_object
class FinderParticipant(CaseParticipant):
    """
    A FinderParticipant is a CaseParticipant that has the FINDER role in a VulnerabilityCase.
    """

    @model_validator(mode="after")
    def post_init_setup(self):
        super().post_init_setup()
        self.add_role(CVDRole.FINDER, reset=True)
        return self


@activitystreams_object
class ReporterParticipant(CaseParticipant):
    """
    A ReporterParticipant is a CaseParticipant that has the REPORTER role in a VulnerabilityCase.
    """

    @model_validator(mode="after")
    def post_init_setup(self):
        super().post_init_setup()
        self.add_role(CVDRole.REPORTER, reset=True)
        # by definition, to be a reporter, you must have accepted the report
        pstatus = ParticipantStatus(
            context=self.context,
            actor=self.actor,
            rm_state=RM.ACCEPTED,
        )
        self.participant_status = [pstatus]
        return self


@activitystreams_object
class FinderReporterParticipant(CaseParticipant):
    """
    A FinderReporterParticipant is a CaseParticipant that has both the FINDER and REPORTER roles in a
    VulnerabilityCase.
    """

    @model_validator(mode="after")
    def post_init_setup(self):
        super().post_init_setup()
        self.add_role(CVDRole.FINDER, reset=True)
        self.add_role(CVDRole.REPORTER, reset=False)

        # by definition, to be a reporter, you must have accepted the report
        pstatus = ParticipantStatus(
            context=self.context,
            actor=self.actor,
            rm_state=RM.ACCEPTED,
        )
        self.participant_status = [pstatus]
        return self


@activitystreams_object
class VendorParticipant(CaseParticipant):
    """
    A VendorParticipant is a CaseParticipant that has the VENDOR role in a VulnerabilityCase.
    """

    @model_validator(mode="after")
    def post_init_setup(self):
        super().post_init_setup()
        self.add_role(CVDRole.VENDOR, reset=True)
        return self


@activitystreams_object
class DeployerParticipant(CaseParticipant):
    """
    A DeployerParticipant is a CaseParticipant that has the DEPLOYER role in a VulnerabilityCase.
    """

    @model_validator(mode="after")
    def post_init_setup(self):
        super().post_init_setup()
        self.add_role(CVDRole.DEPLOYER, reset=True)
        return self


@activitystreams_object
class CoordinatorParticipant(CaseParticipant):
    """
    A CoordinatorParticipant is a CaseParticipant that has the COORDINATOR role in a VulnerabilityCase.
    """

    @model_validator(mode="after")
    def post_init_setup(self):
        super().post_init_setup()
        self.add_role(CVDRole.COORDINATOR, reset=True)
        return self


@activitystreams_object
class OtherParticipant(CaseParticipant):
    """
    An OtherParticipant is a CaseParticipant that has the OTHER role in a VulnerabilityCase.
    """

    @model_validator(mode="after")
    def post_init_setup(self):
        super().post_init_setup()
        self.add_role(CVDRole.OTHER, reset=True)
        return self


def main():
    actor = as_Actor(name="Actor Name")
    cp = CaseParticipant(actor=actor, context="case_id_foo")
    print(f"### {cp.as_type} ###")
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
        obj = role(actor=actor, context="https://for.example/case/99999")
        print(f"### {obj.as_type} ###")
        print()
        print(obj.to_json(indent=2))
        print()
        print()


if __name__ == "__main__":
    main()
