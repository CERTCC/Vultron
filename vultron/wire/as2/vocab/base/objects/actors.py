#!/usr/bin/env python
"""This module provides actor classes"""

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

from typing import Any, TypeAlias

from pydantic import Field, ValidationInfo, field_validator, model_validator

from vultron.wire.as2.enums import as_ActorType as A_type
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.collections import (
    as_OrderedCollection,
)
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP


class as_Actor(as_Object):
    """Base class for all ActivityPub actors.
    Describes one or more entities that performed or are expected to perform an activity.
    Any single activity can have multiple actors.
    The actor may be specified using an indirect Link or as an embedded Object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-actor>
    """

    # todo: collections should be internally represented as lists but dumped as collections
    inbox: as_OrderedCollection = Field(default_factory=as_OrderedCollection)
    outbox: as_OrderedCollection = Field(default_factory=as_OrderedCollection)
    preferred_username: str | None = None
    endpoints: Any | None = None
    # todo endpoints should be its own object
    # see https://www.w3.org/TR/activitypub/#actors

    @field_validator("inbox", "outbox", mode="before")
    @classmethod
    def _coerce_uri_to_collection(cls, v: Any, info: ValidationInfo) -> Any:
        """Coerce a plain URI string or None to an as_OrderedCollection.

        When reading back an actor that was stored via a CoreActor-derived
        class (inbox/outbox as str | None), the value is normalised:

        - ``None`` → ``as_OrderedCollection`` at ``{actor_id}/{field}``, the
          same address ``set_collections`` derives when the field is absent
        - ``str`` → ``as_OrderedCollection(id_=v)``
        - anything else → returned as-is for Pydantic to validate
        """
        if v is None:
            return _endpoint_collection(info.data.get("id_"), info.field_name)
        if isinstance(v, str):
            return as_OrderedCollection(id_=v)
        return v

    @model_validator(mode="after")
    def set_collections(self):
        """Derive an absent ``inbox``/``outbox`` from the actor's ``id_``.

        Keyed on ``model_fields_set`` rather than on the collection's ``id_``:
        the field's ``default_factory`` builds a collection whose ``id_`` is a
        fresh ``urn:uuid:``, so an ``id_ is None`` test never fires and the
        actor would publish an address nobody routes to.
        """
        for field_name in ("inbox", "outbox"):
            if field_name not in self.model_fields_set:
                object.__setattr__(
                    self,
                    field_name,
                    _endpoint_collection(self.id_, field_name),
                )
        return self


def _endpoint_collection(
    actor_id: str | None, field_name: str | None
) -> as_OrderedCollection:
    """Return the collection at the actor's ``{actor_id}/{field_name}`` URL.

    Falls back to a fresh collection id when the actor id is unavailable,
    which happens only if ``id_`` itself failed validation — in which case the
    actor is being rejected anyway.
    """
    if actor_id is None or field_name is None:
        return as_OrderedCollection()
    return as_OrderedCollection(id_=f"{actor_id}/{field_name}")


as_ActorRef: TypeAlias = ActivityStreamRef[as_Actor]


class as_Group(as_Actor):
    """A special kind of actor representing a logical group of persons or other actors.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-group>
    """

    type_: A_type = Field(
        default=A_type.GROUP,
        validation_alias="type",
        serialization_alias="type",
    )


as_GroupRef: TypeAlias = ActivityStreamRef[as_Group]


class as_Organization(as_Actor):
    """A special kind of actor representing a logical group of persons or other actors.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-organization>
    """

    type_: A_type = Field(
        default=A_type.ORGANIZATION,
        validation_alias="type",
        serialization_alias="type",
    )


as_OrganizationRef: TypeAlias = ActivityStreamRef[as_Organization]


class as_Application(as_Actor):
    """A special kind of actor representing a software application.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-application>
    """

    type_: A_type = Field(
        default=A_type.APPLICATION,
        validation_alias="type",
        serialization_alias="type",
    )


as_ApplicationRef: TypeAlias = ActivityStreamRef[as_Application]


class as_Service(as_Actor):
    """A special kind of actor representing a service.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-service>
    A service is a kind of actor that represents a non-human actor.
    """

    type_: A_type = Field(
        default=A_type.SERVICE,
        validation_alias="type",
        serialization_alias="type",
    )


as_ServiceRef: TypeAlias = ActivityStreamRef[as_Service]


class as_Person(as_Actor):
    """A special kind of actor representing an individual person.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-person>
    """

    type_: A_type = Field(
        default=A_type.PERSON,
        validation_alias="type",
        serialization_alias="type",
    )


as_PersonRef: TypeAlias = ActivityStreamRef[as_Person]

# as_Actor has no concrete type_ annotation of its own but is used as a
# concrete stored type with type_='Actor' via set_type_from_class_name().
WIRE_TYPE_MAP["Actor"] = as_Actor


def main():
    from vultron.wire.as2.vocab.base.utils import print_object_examples

    print_object_examples()


if __name__ == "__main__":
    main()
