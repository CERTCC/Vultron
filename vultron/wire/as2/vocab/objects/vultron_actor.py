#!/usr/bin/env python
"""
Provides Vultron-extended Actor classes for the Vultron ActivityStreams
Vocabulary.

These subclasses extend the standard ActivityStreams actor types with optional
Vultron-specific profile fields, such as an actor's embargo policy.

The actor's ActivityStreams type (Person, Organization, Service) is preserved,
ensuring interoperability with ActivityPub clients that do not understand
Vultron extensions.

JSON-LD Context Note
--------------------
A fully interoperable implementation would extend the JSON-LD ``@context``
to define Vultron terms such as ``embargoPolicy`` under a Vultron namespace
(e.g., ``https://vultron.sei.cmu.edu/ns#``).  That wiring is deferred to a
later milestone; see ``plan/IMPLEMENTATION_NOTES.md`` for details.

Per ``specs/embargo-policy.md`` EP-01-001.
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

from typing import TypeAlias

from pydantic import BaseModel, Field

from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Organization,
    as_Person,
    as_Service,
)
from vultron.wire.as2.vocab.objects.embargo_policy import EmbargoPolicyRef


class VultronActorMixin(BaseModel):
    """
    Mixin that adds Vultron-specific optional profile fields to any
    ActivityStreams Actor subclass.

    Intended for use via multiple inheritance alongside an actor type
    (e.g., ``as_Person``, ``as_Organization``).
    """

    embargo_policy: EmbargoPolicyRef | None = Field(
        default=None,
        description="The actor's stated embargo preferences (EP-01-001)",
    )


class VultronPerson(VultronActorMixin, as_Person):
    """
    An ActivityStreams Person extended with Vultron profile fields.

    Retains ``type_ == "Person"`` for ActivityPub interoperability.
    """


VultronPersonRef: TypeAlias = ActivityStreamRef[VultronPerson]


class VultronOrganization(VultronActorMixin, as_Organization):
    """
    An ActivityStreams Organization extended with Vultron profile fields.

    Retains ``type_ == "Organization"`` for ActivityPub interoperability.
    """


VultronOrganizationRef: TypeAlias = ActivityStreamRef[VultronOrganization]


class VultronService(VultronActorMixin, as_Service):
    """
    An ActivityStreams Service extended with Vultron profile fields.

    Retains ``type_ == "Service"`` for ActivityPub interoperability.
    """


VultronServiceRef: TypeAlias = ActivityStreamRef[VultronService]
