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

from vultron.as_vocab.base import activitystreams_object
from vultron.as_vocab.base.links import ActivityStreamRef
from vultron.as_vocab.base.objects.base import as_Object, as_ObjectRef


@activitystreams_object
class as_Document(as_Object):
    """Base class for all ActivityPub documents. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-document>"""


@activitystreams_object
class as_Image(as_Document):
    """Base class for all ActivityPub images. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-image>"""


@activitystreams_object
class as_Video(as_Document):
    """Base class for all ActivityPub videos. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-video>"""


@activitystreams_object
class as_Audio(as_Document):
    """Base class for all ActivityPub audio. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-audio>"""


@activitystreams_object
class as_Page(as_Document):
    """Base class for all ActivityPub pages. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-page>"""


@activitystreams_object
class as_Article(as_Document):
    """Base class for all ActivityPub articles. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-article>"""


# A Document can be any of its subclasses
as_DocumentRef: TypeAlias = ActivityStreamRef[as_Document]


@activitystreams_object
class as_Note(as_Object):
    """Base class for all ActivityPub notes. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-note>"""


as_NoteRef: TypeAlias = ActivityStreamRef[as_Note]


@activitystreams_object
class as_Event(as_Object):
    """Base class for all ActivityPub events. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-event>"""


as_EventRef: TypeAlias = ActivityStreamRef[as_Event]


@activitystreams_object
class as_Profile(as_Object):
    """Base class for all ActivityPub profiles. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-profile>"""

    describes: as_ObjectRef | None = None


as_ProfileRef: TypeAlias = ActivityStreamRef[as_Profile]


@activitystreams_object
class as_Tombstone(as_Object):
    """Base class for all ActivityPub tombstones. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-tombstone>"""

    former_type: str | None = None
    deleted: datetime | None = None


as_TombstoneRef: TypeAlias = ActivityStreamRef[as_Tombstone]


@activitystreams_object
class as_Relationship(as_Object):
    """Base class for all ActivityPub relationships. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-relationship>"""

    subject: as_ObjectRef | None = None
    object: as_ObjectRef | None = None
    # TODO: should relationship be a str or uri? Usually it'd be a term from https://vocab.org/relationship/ http://xmlns.com/foaf/spec/
    relationship: str | None = None


as_RelationshipRef: TypeAlias = ActivityStreamRef[as_Relationship]


@activitystreams_object
class as_Place(as_Object):
    """Base class for all ActivityPub places. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-place>"""

    longitude: float | None = None
    latitude: float | None = None
    altitude: float | None = None
    radius: float | None = None
    accuracy: float | None = None
    units: str | None = None


as_PlaceRef: TypeAlias = ActivityStreamRef[as_Place]


def main():
    from vultron.as_vocab.base.utils import print_object_examples

    print_object_examples()


if __name__ == "__main__":
    main()
