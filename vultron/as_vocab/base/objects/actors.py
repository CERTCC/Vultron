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

from dataclasses import dataclass, field
from typing import Any, Optional

from dataclasses_json import LetterCase, dataclass_json

from vultron.as_vocab.base import activitystreams_object
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.base.objects.collections import (
    as_Collection,
    as_OrderedCollection,
)


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class as_Actor(as_Object):
    """Base class for all ActivityPub actors.
    Describes one or more entities that performed or are expected to perform an activity.
    Any single activity can have multiple actors.
    The actor may be specified using an indirect Link or as an embedded Object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-actor>
    """

    # todo: collections should be internally represented as lists but dumped as collections
    inbox: as_OrderedCollection = field(default_factory=as_OrderedCollection)
    outbox: as_OrderedCollection = field(default_factory=as_OrderedCollection)
    following: Optional[as_Collection] = None
    followers: Optional[as_Collection] = None
    liked: Optional[as_Collection] = None
    streams: Optional[as_Collection] = None
    preferred_username: Optional[str] = None
    endpoints: Optional[Any] = None
    # todo endpoints should be its own object
    # see https://www.w3.org/TR/activitypub/#actors


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class as_Group(as_Actor):
    """A special kind of actor representing a logical group of persons or other actors.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-group>
    """


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class as_Organization(as_Actor):
    """A special kind of actor representing a logical group of persons or other actors.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-organization>
    """


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class as_Application(as_Actor):
    """A special kind of actor representing a software application.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-application>
    """


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class as_Service(as_Actor):
    """A special kind of actor representing a service.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-service>
    A service is a kind of actor that represents a non-human actor.
    """


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class as_Person(as_Actor):
    """A special kind of actor representing an individual person.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-person>
    """


def main():
    from vultron.as_vocab.base.utils import print_object_examples

    print_object_examples()


if __name__ == "__main__":
    main()
