#!/usr/bin/env python
"""
Wire-layer aliases for Vultron actor types.

Per ADR-0099 detail 3: core actor classes are the canonical form.
The as_-prefixed names and WIRE_TYPE_MAP entries are retained for
backward compatibility and vocabulary lookup.
"""

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
    CoreActor,
    VultronApplication,
    VultronGroup,
    VultronOrganization,
    VultronPerson,
    VultronService,
)
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP

# Backward-compatibility aliases (ADR-0099 detail 3)
as_VultronPerson = VultronPerson
as_VultronOrganization = VultronOrganization
as_VultronService = VultronService
as_VultronApplication = VultronApplication
as_VultronGroup = VultronGroup

# Register core actor classes in WIRE_TYPE_MAP for wire type-string lookup
# (e.g. incoming JSON with "type": "Person") and for render() class-name lookup.
WIRE_TYPE_MAP["Person"] = VultronPerson
WIRE_TYPE_MAP["Organization"] = VultronOrganization
WIRE_TYPE_MAP["Service"] = VultronService
WIRE_TYPE_MAP["Application"] = VultronApplication
WIRE_TYPE_MAP["Group"] = VultronGroup

# Class-name entries so As2WireRenderAdapter.render() can locate the type by
# type(obj).__name__ (e.g. "VultronPerson").
WIRE_TYPE_MAP["VultronPerson"] = VultronPerson
WIRE_TYPE_MAP["VultronOrganization"] = VultronOrganization
WIRE_TYPE_MAP["VultronService"] = VultronService
WIRE_TYPE_MAP["VultronApplication"] = VultronApplication
WIRE_TYPE_MAP["VultronGroup"] = VultronGroup

as_VultronPersonRef: TypeAlias = ActivityStreamRef[VultronPerson]
as_VultronOrganizationRef: TypeAlias = ActivityStreamRef[VultronOrganization]
as_VultronServiceRef: TypeAlias = ActivityStreamRef[VultronService]
as_VultronApplicationRef: TypeAlias = ActivityStreamRef[VultronApplication]
as_VultronGroupRef: TypeAlias = ActivityStreamRef[VultronGroup]


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
    "CoreActor",
    "as_VultronApplication",
    "as_VultronApplicationRef",
    "as_VultronGroup",
    "as_VultronGroupRef",
    "as_VultronOrganization",
    "as_VultronOrganizationRef",
    "as_VultronPerson",
    "as_VultronPersonRef",
    "as_VultronService",
    "as_VultronServiceRef",
]
