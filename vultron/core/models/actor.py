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

from typing import Any, Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

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
    delegated to the DataLayer, accessed via DataLayer.  An endpoint that
    arrives absent or ``None`` is derived from ``id_`` (``{id_}/inbox``),
    because these classes are also the wire form (ADR-0099) and ActivityPub
    requires every actor to publish both (ISSUE-3616).
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

    @model_validator(mode="after")
    def _derive_endpoints_from_id(self) -> Self:
        """Fill an absent or ``None`` ``inbox``/``outbox`` from ``id_``.

        Mirrors ``as_Actor.set_collections`` so a Vultron actor publishes the
        same addresses whichever branch built it.  Written with
        ``object.__setattr__`` so ``validate_assignment`` does not re-enter
        this validator, and recorded in ``model_fields_set`` so an
        ``exclude_unset`` dump still carries the derived address.
        """
        for field_name in ("inbox", "outbox"):
            if getattr(self, field_name) is None:
                object.__setattr__(
                    self, field_name, f"{self.id_}/{field_name}"
                )
                self.model_fields_set.add(field_name)
        return self

    preferred_username: str | None = None
    endpoints: Any | None = None
    embargo_policy: Any | None = Field(
        default=None,
        description="The actor's stated embargo preferences.",
    )


class VultronPerson(CoreActor):
    """Core domain model for a Person actor."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_name=True,
        validate_by_alias=True,
    )
    type_: Literal[VultronActorType.PERSON] = Field(
        default=VultronActorType.PERSON,
        validation_alias="type",
        serialization_alias="type",
    )


class VultronOrganization(CoreActor):
    """Core domain model for an Organization actor."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_name=True,
        validate_by_alias=True,
    )
    type_: Literal[VultronActorType.ORGANIZATION] = Field(
        default=VultronActorType.ORGANIZATION,
        validation_alias="type",
        serialization_alias="type",
    )


class VultronService(CoreActor):
    """Core domain model for a Service actor."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_name=True,
        validate_by_alias=True,
    )
    type_: Literal[VultronActorType.SERVICE] = Field(
        default=VultronActorType.SERVICE,
        validation_alias="type",
        serialization_alias="type",
    )


class VultronApplication(CoreActor):
    """Core domain model for an Application actor."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_name=True,
        validate_by_alias=True,
    )
    type_: Literal[VultronActorType.APPLICATION] = Field(
        default=VultronActorType.APPLICATION,
        validation_alias="type",
        serialization_alias="type",
    )


class VultronGroup(CoreActor):
    """Core domain model for a Group actor."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_name=True,
        validate_by_alias=True,
    )
    type_: Literal[VultronActorType.GROUP] = Field(
        default=VultronActorType.GROUP,
        validation_alias="type",
        serialization_alias="type",
    )


__all__ = [
    "CoreActor",
    "VultronApplication",
    "VultronGroup",
    "VultronOrganization",
    "VultronPerson",
    "VultronService",
]
