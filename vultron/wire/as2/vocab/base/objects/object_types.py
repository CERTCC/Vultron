#!/usr/bin/env python
"""This module provides activity streams object classes"""

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

from datetime import datetime
from typing import TypeAlias

from pydantic import Field

from vultron.wire.as2.enums import as_ObjectType as O_type
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.objects.base import as_Object, as_ObjectRef


class as_Document(as_Object):
    """Base class for all ActivityPub documents. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-document>"""

    type_: O_type = Field(
        default=O_type.DOCUMENT,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Image(as_Document):
    """Base class for all ActivityPub images. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-image>"""

    type_: O_type = Field(
        default=O_type.IMAGE,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Video(as_Document):
    """Base class for all ActivityPub videos. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-video>"""

    type_: O_type = Field(
        default=O_type.VIDEO,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Audio(as_Document):
    """Base class for all ActivityPub audio. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-audio>"""

    type_: O_type = Field(
        default=O_type.AUDIO,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Page(as_Document):
    """Base class for all ActivityPub pages. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-page>"""

    type_: O_type = Field(
        default=O_type.PAGE,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Article(as_Document):
    """Base class for all ActivityPub articles. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-article>"""

    type_: O_type = Field(
        default=O_type.ARTICLE,
        validation_alias="type",
        serialization_alias="type",
    )


# A Document can be any of its subclasses
as_DocumentRef: TypeAlias = ActivityStreamRef[as_Document]


class as_Note(as_Object):
    """Base class for all ActivityPub notes. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-note>"""

    type_: O_type = Field(
        default=O_type.NOTE,
        validation_alias="type",
        serialization_alias="type",
    )

    # notes must have content
    content: str = Field(default="")


as_NoteRef: TypeAlias = ActivityStreamRef[as_Note]


class as_Event(as_Object):
    """Base class for all ActivityPub events. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-event>"""

    type_: O_type = Field(
        default=O_type.EVENT,
        validation_alias="type",
        serialization_alias="type",
    )


as_EventRef: TypeAlias = ActivityStreamRef[as_Event]


class as_Profile(as_Object):
    """Base class for all ActivityPub profiles. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-profile>"""

    type_: O_type = Field(
        default=O_type.PROFILE,
        validation_alias="type",
        serialization_alias="type",
    )

    describes: as_ObjectRef | None = None


as_ProfileRef: TypeAlias = ActivityStreamRef[as_Profile]


class as_Tombstone(as_Object):
    """Base class for all ActivityPub tombstones. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-tombstone>"""

    type_: O_type = Field(
        default=O_type.TOMBSTONE,
        validation_alias="type",
        serialization_alias="type",
    )

    former_type: str | None = None
    deleted: datetime | None = None


as_TombstoneRef: TypeAlias = ActivityStreamRef[as_Tombstone]


class as_Relationship(as_Object):
    """Base class for all ActivityPub relationships. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-relationship>"""

    type_: O_type = Field(
        default=O_type.RELATIONSHIP,
        validation_alias="type",
        serialization_alias="type",
    )

    subject: as_ObjectRef | None = None
    object: as_ObjectRef | None = None
    # TODO: should relationship be a str or uri? Usually it'd be a term from https://vocab.org/relationship/ http://xmlns.com/foaf/spec/
    relationship: str | None = None


as_RelationshipRef: TypeAlias = ActivityStreamRef[as_Relationship]


class as_Place(as_Object):
    """Base class for all ActivityPub places. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-place>"""

    type_: O_type = Field(
        default=O_type.PLACE,
        validation_alias="type",
        serialization_alias="type",
    )

    longitude: float | None = None
    latitude: float | None = None
    altitude: float | None = None
    radius: float | None = None
    accuracy: float | None = None
    units: str | None = None


as_PlaceRef: TypeAlias = ActivityStreamRef[as_Place]


def main():
    from vultron.wire.as2.vocab.base.utils import print_object_examples

    print_object_examples()


if __name__ == "__main__":
    main()
