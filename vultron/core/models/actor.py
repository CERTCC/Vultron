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

from pydantic import ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from vultron.core.models.base import CoreObject


class CoreActor(CoreObject):
    """Base domain model for Vultron actors.

    The core actor hierarchy carries the shared Vultron-specific extension
    fields that were previously defined only in the wire layer. Concrete
    actor types inherit from this base and add a concrete ``type_``
    discriminator.
    """

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
    inbox: CoreActorCollection | None = None
    outbox: CoreActorCollection | None = None
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

    @model_validator(mode="after")
    def _ensure_actor_collections(self) -> "CoreActor":
        actor_id = self.id_
        if self.inbox is None:
            self.inbox = CoreActorCollection(id_=f"{actor_id}/inbox")
        if self.outbox is None:
            self.outbox = CoreActorCollection(id_=f"{actor_id}/outbox")
        return self

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
    type_: Literal["Person"] = Field(
        default="Person",
        validation_alias="type",
        serialization_alias="type",
    )


class VultronOrganization(CoreActor):
    type_: Literal["Organization"] = Field(
        default="Organization",
        validation_alias="type",
        serialization_alias="type",
    )


class VultronService(CoreActor):
    type_: Literal["Service"] = Field(
        default="Service",
        validation_alias="type",
        serialization_alias="type",
    )


class VultronApplication(CoreActor):
    type_: Literal["Application"] = Field(
        default="Application",
        validation_alias="type",
        serialization_alias="type",
    )


class VultronGroup(CoreActor):
    type_: Literal["Group"] = Field(
        default="Group",
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
