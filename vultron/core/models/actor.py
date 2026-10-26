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

from typing import Any, Literal, Self, TypedDict

from pydantic import ConfigDict, Field, field_validator, model_validator

from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.models.enums import VultronActorType


class CoreActor(CoreObject):
    """Base domain model for Vultron actors.

    The core actor hierarchy carries the shared Vultron-specific extension
    fields that were previously defined only in the wire layer. Concrete
    actor types inherit from this base and add a concrete ``type_``
    discriminator.

    Note: inbox and outbox are simple string URIs representing the
    actor's ActivityStreams collection endpoints. Queue persistence is
    delegated to the DataLayer, accessed via DataLayer.  An endpoint is
    absent unless the profile states it: a record of a peer holds only what
    the peer's profile supplied, and an address derived from the id would be
    a value nobody asserted (AKM-02-006, ADR-0159).  A hosted actor states its
    own endpoints when it is created (:func:`hosted_endpoints`), so the
    profile it publishes carries both, as ActivityPub requires (ISSUE-3616).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_name=True,
    )

    inbox: NonEmptyString | None = None
    outbox: NonEmptyString | None = None

    @field_validator("inbox", "outbox", mode="before")
    @classmethod
    def _coerce_collection_to_uri(cls, v: Any) -> str | None:
        """Coerce a collection object to its URI string.

        When reading back from storage, inbox/outbox may be stored as a full
        collection dict (from wire-layer as_Service/as_Actor) rather than a
        plain string URI. Extract the id_ or id field for backward compat.
        ``None``, a blank string or a collection without an id reads as
        ``None``: none of them names an address.  A collection model whose
        ``id_`` was never set (the parser expands an inline id-less
        collection before this runs) counts as having no id: its ``id_`` is a
        freshly minted ``urn:uuid:`` nobody routes to.
        """
        if v is None:
            return None
        if isinstance(v, str):
            return v.strip() or None
        if isinstance(v, dict):
            return str(v.get("id_") or v.get("id") or "").strip() or None
        fields_set = getattr(v, "model_fields_set", None)
        if fields_set is not None and "id_" not in fields_set:
            return None
        return (
            str(
                getattr(v, "id_", None) or getattr(v, "id", None) or ""
            ).strip()
            or None
        )

    preferred_username: NonEmptyString | None = None
    endpoints: Any | None = None
    embargo_policy: EmbargoPolicy | None = Field(
        default=None,
        description=(
            "The actor's published embargo policy, carried inline as part of"
            " the profile (EP-01-001)."
        ),
    )

    @field_validator("embargo_policy", mode="before")
    @classmethod
    def _refuse_policy_reference(cls, v: Any) -> Any:
        """Refuse a policy named by URL, the pre-#4027 stored shape (EP-01-001).

        The old embargo-policy PUT stored the policy as a free-standing
        record and put its URL on the actor.  The policy is now a field of
        the profile, so a URL is refused with a message saying so, rather
        than a bare type error; a store written before the change must be
        reset, because no silent conversion is made.
        """
        if isinstance(v, str):
            raise ValueError(  # noqa: TRY004 — Pydantic needs ValueError
                f"embargoPolicy is a reference ({v!r}), but the policy must be"
                " carried inline in the actor profile (EP-01-001); an actor"
                " record stored by the pre-#4027 embargo-policy PUT holds this"
                " shape, and its store must be reset"
            )
        return v

    @model_validator(mode="after")
    def _embargo_policy_names_this_actor(self) -> Self:
        """Refuse a profile carrying another actor's policy (EP-01-001).

        The policy is a field of the profile, so the actor it applies to is
        the profile's own.  A profile whose ``embargoPolicy.actorId`` names
        someone else would hand that actor's terms to whoever reads this
        profile as its owner's actor default (CP-01-010).
        """
        policy = self.embargo_policy
        if policy is not None and policy.actor_id != self.id_:
            raise ValueError(
                f"embargoPolicy.actorId {policy.actor_id!r} differs from the"
                f" profile id {self.id_!r}: an actor profile carries only its"
                " own embargo policy (EP-01-001, CP-01-010)"
            )
        return self


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


class HostedEndpoints(TypedDict):
    """The ``inbox`` and ``outbox`` keyword arguments of a hosted actor."""

    inbox: str
    outbox: str


def hosted_endpoints(actor_id: str) -> HostedEndpoints:
    """The ``inbox`` and ``outbox`` a hosted actor states in its own profile.

    For the actor this node hosts, and only for it: the node routes
    ``{actor_id}/inbox`` and ``{actor_id}/outbox``, so they are values the
    actor knows.  For a peer the same addresses would be guesses
    (AKM-02-006); delivery falls back to the derived inbox address itself
    when it holds none (OX-12-009).
    """
    return HostedEndpoints(
        inbox=f"{actor_id}/inbox", outbox=f"{actor_id}/outbox"
    )


__all__ = [
    "CoreActor",
    "HostedEndpoints",
    "VultronApplication",
    "VultronGroup",
    "VultronOrganization",
    "VultronPerson",
    "VultronService",
    "hosted_endpoints",
]
