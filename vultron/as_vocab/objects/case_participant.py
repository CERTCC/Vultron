#!/usr/bin/env python
"""
Provides various CaseParticipant objects for the Vultron ActivityStreams Vocabulary.
"""
#  Copyright (c) 2023-2024 Carnegie Mellon University and Contributors.
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

from dataclasses import dataclass, field
from typing import Union

from dataclasses_json import LetterCase, config, dataclass_json

from vultron.as_vocab.base import activitystreams_object
from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.base.utils import exclude_if_none
from vultron.as_vocab.objects.base import VultronObject
from vultron.as_vocab.objects.case_status import ParticipantStatus
from vultron.bt.roles.states import CVDRoles as CVDRole


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
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

    actor: as_Actor
    name: str
    # context: Union[as_Object, as_Link]
    case_roles: list[CVDRole] = field(
        default_factory=list,
        metadata=config(
            encoder=lambda x: [CVDRole(value).name for value in x],
            decoder=lambda x: [CVDRole[name] for name in x],
        ),
    )
    participant_status: list[ParticipantStatus] = field(default_factory=list)
    participant_case_name: str = field(
        default=None, metadata=config(exclude=exclude_if_none)
    )
    context: Union["VulnerabilityCase", as_Link] = field(
        default=None, repr=True
    )

    def __post_init__(self):
        super().__post_init__()
        if len(self.case_roles) == 0:
            # if they didn't specify a role, put NO_ROLE here
            self.case_roles.append(CVDRole.NO_ROLE)

        if self.actor is not None:
            self.name = self.actor.name

        if len(self.participant_status) == 0:
            self.participant_status.append(ParticipantStatus())

        if len(self.case_roles) == 0:
            self.case_roles.append(CVDRole.NO_ROLE)

    def add_role(self, role, reset=False):
        if reset:
            self.case_roles = []
        self.case_roles.append(role)


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class FinderParticipant(CaseParticipant):
    """
    A FinderParticipant is a CaseParticipant that has the FINDER role in a VulnerabilityCase.
    """

    as_type = "CaseParticipant"

    def __post_init__(self):
        super().__post_init__()
        self.add_role(CVDRole.FINDER, reset=True)


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class ReporterParticipant(CaseParticipant):
    """
    A ReporterParticipant is a CaseParticipant that has the REPORTER role in a VulnerabilityCase.
    """

    as_type = "CaseParticipant"

    def __post_init__(self):
        super().__post_init__()
        self.add_role(CVDRole.REPORTER, reset=True)


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class FinderReporterParticipant(CaseParticipant):
    """
    A FinderReporterParticipant is a CaseParticipant that has both the FINDER and REPORTER roles in a
    VulnerabilityCase.
    """

    as_type = "CaseParticipant"

    def __post_init__(self):
        super().__post_init__()
        self.add_role(CVDRole.FINDER, reset=True)
        self.add_role(CVDRole.REPORTER, reset=False)


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class VendorParticipant(CaseParticipant):
    """
    A VendorParticipant is a CaseParticipant that has the VENDOR role in a VulnerabilityCase.
    """

    as_type = "CaseParticipant"

    def __post_init__(self):
        super().__post_init__()
        self.add_role(CVDRole.VENDOR, reset=True)


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class DeployerParticipant(CaseParticipant):
    """
    A DeployerParticipant is a CaseParticipant that has the DEPLOYER role in a VulnerabilityCase.
    """

    as_type = "CaseParticipant"

    def __post_init__(self):
        super().__post_init__()
        self.add_role(CVDRole.DEPLOYER, reset=True)


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class CoordinatorParticipant(CaseParticipant):
    """
    A CoordinatorParticipant is a CaseParticipant that has the COORDINATOR role in a VulnerabilityCase.
    """

    as_type = "CaseParticipant"

    def __post_init__(self):
        super().__post_init__()
        self.add_role(CVDRole.COORDINATOR, reset=True)


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class OtherParticipant(CaseParticipant):
    """
    An OtherParticipant is a CaseParticipant that has the OTHER role in a VulnerabilityCase.
    """

    def __post_init__(self):
        super().__post_init__()
        self.add_role(CVDRole.OTHER, reset=True)


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
