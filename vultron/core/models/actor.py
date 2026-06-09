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

"""Core domain representations for Vultron actors."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from vultron.core.models.base import CoreObject
from vultron.core.models.enums import VultronActorType


class CoreActor(CoreObject):
    """Base domain model for Vultron actors.

    The core actor hierarchy carries the shared Vultron-specific extension
    fields that were previously defined only in the wire layer. Concrete
    actor types inherit from this base and add a concrete ``type_``
    discriminator.

    Note: inbox and outbox are now simple string URIs representing the
    actor's ActivityStreams collection endpoints. Queue persistence is
    delegated to the DataLayer, accessed via ActorScopedDataLayer.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_name=True,
    )

    inbox: str | None = None
    outbox: str | None = None

    @field_validator("inbox", "outbox", mode="before")
    @classmethod
    def _coerce_collection_to_uri(cls, v: Any) -> str | None:
        """Coerce a collection object to its URI string.

        When reading back from storage, inbox/outbox may be stored as a full
        collection dict (from wire-layer as_Service/as_Actor) rather than a
        plain string URI. Extract the id_ or id field for backward compat.
        """
        if v is None or isinstance(v, str):
            return v
        if isinstance(v, dict):
            return v.get("id_") or v.get("id") or None
        return getattr(v, "id_", None) or getattr(v, "id", None) or None

    following: Any | None = None
    followers: Any | None = None
    liked: Any | None = None
    streams: Any | None = None
    preferred_username: str | None = None
    endpoints: Any | None = None
    embargo_policy: Any | None = Field(
        default=None,
        description="The actor's stated embargo preferences.",
    )

    def to_json(self, **kwargs: Any) -> str:
        return self.model_dump_json(exclude_none=True, by_alias=True, **kwargs)


class CoreActorCollection(CoreObject):
    """Minimal ordered-collection shape used for actor inbox/outbox fields."""

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
    )

    context_: str = Field(
        default="https://www.w3.org/ns/activitystreams",
        validation_alias="@context",
        serialization_alias="@context",
    )
    type_: Literal["OrderedCollection"] = Field(
        default="OrderedCollection",
        validation_alias="type",
        serialization_alias="type",
    )
    items: list[str] = Field(default_factory=list)
    current: int = 0


class VultronPerson(CoreActor):
    """Core domain model for a Person actor.

    Registered in VOCABULARY["Person"]; uses camelCase aliases for AS2 wire
    serialization.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_name=True,
        validate_by_alias=True,
        alias_generator=to_camel,
    )
    type_: Literal[VultronActorType.PERSON] = Field(
        default=VultronActorType.PERSON,
        validation_alias="type",
        serialization_alias="type",
    )


class VultronOrganization(CoreActor):
    """Core domain model for an Organization actor.

    Registered in VOCABULARY["Organization"]; uses camelCase aliases for AS2
    wire serialization.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_name=True,
        validate_by_alias=True,
        alias_generator=to_camel,
    )
    type_: Literal[VultronActorType.ORGANIZATION] = Field(
        default=VultronActorType.ORGANIZATION,
        validation_alias="type",
        serialization_alias="type",
    )


class VultronService(CoreActor):
    """Core domain model for a Service actor.

    Registered in VOCABULARY["Service"]; uses camelCase aliases for AS2 wire
    serialization.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_name=True,
        validate_by_alias=True,
        alias_generator=to_camel,
    )
    type_: Literal[VultronActorType.SERVICE] = Field(
        default=VultronActorType.SERVICE,
        validation_alias="type",
        serialization_alias="type",
    )


class VultronApplication(CoreActor):
    """Core domain model for an Application actor.

    Registered in VOCABULARY["Application"]; uses camelCase aliases for AS2
    wire serialization.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_name=True,
        validate_by_alias=True,
        alias_generator=to_camel,
    )
    type_: Literal[VultronActorType.APPLICATION] = Field(
        default=VultronActorType.APPLICATION,
        validation_alias="type",
        serialization_alias="type",
    )


class VultronGroup(CoreActor):
    """Core domain model for a Group actor.

    Registered in VOCABULARY["Group"]; uses camelCase aliases for AS2 wire
    serialization.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_name=True,
        validate_by_alias=True,
        alias_generator=to_camel,
    )
    type_: Literal[VultronActorType.GROUP] = Field(
        default=VultronActorType.GROUP,
        validation_alias="type",
        serialization_alias="type",
    )


# Backward-compatibility alias; the new core base is the canonical home.
VultronActorMixin = CoreActor


__all__ = [
    "CoreActor",
    "CoreActorCollection",
    "VultronActorMixin",
    "VultronApplication",
    "VultronGroup",
    "VultronOrganization",
    "VultronPerson",
    "VultronService",
]
