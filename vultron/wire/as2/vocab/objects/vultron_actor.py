#!/usr/bin/env python
"""Wire-branch Vultron actor models."""

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

from typing import Annotated, Any, Literal, TypeAlias, Union

from pydantic import Field

from vultron.wire.as2.enums import as_ActorType
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.registry import VOCABULARY


class VultronActorMixin(as_Actor):
    """Wire actor base with Vultron-specific actor extension fields."""

    embargo_policy: Any | None = Field(
        default=None,
        description="The actor's stated embargo preferences.",
    )


class VultronPerson(VultronActorMixin):
    type_: Literal[as_ActorType.PERSON] = Field(
        default=as_ActorType.PERSON,
        validation_alias="type",
        serialization_alias="type",
    )


class VultronOrganization(VultronActorMixin):
    type_: Literal[as_ActorType.ORGANIZATION] = Field(
        default=as_ActorType.ORGANIZATION,
        validation_alias="type",
        serialization_alias="type",
    )


class VultronService(VultronActorMixin):
    type_: Literal[as_ActorType.SERVICE] = Field(
        default=as_ActorType.SERVICE,
        validation_alias="type",
        serialization_alias="type",
    )


class VultronApplication(VultronActorMixin):
    type_: Literal[as_ActorType.APPLICATION] = Field(
        default=as_ActorType.APPLICATION,
        validation_alias="type",
        serialization_alias="type",
    )


class VultronGroup(VultronActorMixin):
    type_: Literal[as_ActorType.GROUP] = Field(
        default=as_ActorType.GROUP,
        validation_alias="type",
        serialization_alias="type",
    )


VOCABULARY["Person"] = VultronPerson
VOCABULARY["Organization"] = VultronOrganization
VOCABULARY["Service"] = VultronService
VOCABULARY["Application"] = VultronApplication
VOCABULARY["Group"] = VultronGroup


VultronPersonRef: TypeAlias = ActivityStreamRef[VultronPerson]
VultronOrganizationRef: TypeAlias = ActivityStreamRef[VultronOrganization]
VultronServiceRef: TypeAlias = ActivityStreamRef[VultronService]
VultronApplicationRef: TypeAlias = ActivityStreamRef[VultronApplication]
VultronGroupRef: TypeAlias = ActivityStreamRef[VultronGroup]


ActorUnion: TypeAlias = Annotated[
    Union[
        VultronPerson,
        VultronOrganization,
        VultronService,
        VultronApplication,
        VultronGroup,
    ],
    Field(
        description="A concrete Vultron actor (Person, Organization, Service, Application, or Group)."
    ),
]


__all__ = [
    "ActorUnion",
    "VultronActorMixin",
    "VultronApplication",
    "VultronApplicationRef",
    "VultronGroup",
    "VultronGroupRef",
    "VultronOrganization",
    "VultronOrganizationRef",
    "VultronPerson",
    "VultronPersonRef",
    "VultronService",
    "VultronServiceRef",
]
