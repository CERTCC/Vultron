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

# Register core actor classes in WIRE_TYPE_MAP under their emitted ``type``
# value, so an inbound ``{"type": "Person"}`` deserializes to ``VultronPerson``,
# which carries ``embargo_policy`` — the base ``as_Person`` would drop it. These
# deliberately shadow the ``actors.py`` registrations; this module imports
# ``actors`` so it always registers second. No class-name key is registered:
# ``VultronPerson`` is no payload's ``type`` value (VM-01-008, #2982).
WIRE_TYPE_MAP["Person"] = VultronPerson
WIRE_TYPE_MAP["Organization"] = VultronOrganization
WIRE_TYPE_MAP["Service"] = VultronService
WIRE_TYPE_MAP["Application"] = VultronApplication
WIRE_TYPE_MAP["Group"] = VultronGroup

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
