#!/usr/bin/env python
"""Wire projections for the Vultron actor domain models."""

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

from typing import Annotated, TypeAlias, Union

from pydantic import Field

from vultron.core.models.actor import (
    CoreActor as VultronActorMixin,
    VultronApplication,
    VultronGroup,
    VultronOrganization,
    VultronPerson,
    VultronService,
)
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.registry import VOCABULARY

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
