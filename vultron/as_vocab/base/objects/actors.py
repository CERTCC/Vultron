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

from pydantic import Field, model_validator

from vultron.enums import as_ActorType as A_type
from vultron.as_vocab.base.links import ActivityStreamRef
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.base.objects.collections import (
    as_Collection,
    as_OrderedCollection,
)
from vultron.as_vocab.base.registry import activitystreams_object


@activitystreams_object
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
    following: as_Collection | None = None
    followers: as_Collection | None = None
    liked: as_Collection | None = None
    streams: as_Collection | None = None
    preferred_username: str | None = None
    endpoints: Any | None = None
    # todo endpoints should be its own object
    # see https://www.w3.org/TR/activitypub/#actors

    @model_validator(mode="after")
    def set_collections(self):
        actor_id = self.as_id

        self.inbox = as_OrderedCollection(
            id=f"{actor_id}/inbox", type="OrderedCollection"
        )
        self.outbox = as_OrderedCollection(
            id=f"{actor_id}/outbox", type="OrderedCollection"
        )

        return self


as_ActorRef: TypeAlias = ActivityStreamRef[as_Actor]


@activitystreams_object
class as_Group(as_Actor):
    """A special kind of actor representing a logical group of persons or other actors.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-group>
    """

    as_type: A_type = Field(default=A_type.GROUP, alias="type")


as_GroupRef: TypeAlias = ActivityStreamRef[as_Group]


@activitystreams_object
class as_Organization(as_Actor):
    """A special kind of actor representing a logical group of persons or other actors.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-organization>
    """

    as_type: A_type = Field(default=A_type.ORGANIZATION, alias="type")


as_OrganizationRef: TypeAlias = ActivityStreamRef[as_Organization]


@activitystreams_object
class as_Application(as_Actor):
    """A special kind of actor representing a software application.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-application>
    """

    as_type: A_type = Field(default=A_type.APPLICATION, alias="type")


as_ApplicationRef: TypeAlias = ActivityStreamRef[as_Application]


@activitystreams_object
class as_Service(as_Actor):
    """A special kind of actor representing a service.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-service>
    A service is a kind of actor that represents a non-human actor.
    """

    as_type: A_type = Field(default=A_type.SERVICE, alias="type")


as_ServiceRef: TypeAlias = ActivityStreamRef[as_Service]


@activitystreams_object
class as_Person(as_Actor):
    """A special kind of actor representing an individual person.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-person>
    """

    as_type: A_type = Field(default=A_type.PERSON, alias="type")


as_PersonRef: TypeAlias = ActivityStreamRef[as_Person]


def main():
    from vultron.as_vocab.base.utils import print_object_examples

    print_object_examples()


if __name__ == "__main__":
    main()
