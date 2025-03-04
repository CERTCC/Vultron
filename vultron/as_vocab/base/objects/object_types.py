#!/usr/bin/env python
"""file: object_types
author: adh
created_at: 12/8/22 4:11 PM
"""
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

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from dataclasses_json import LetterCase, dataclass_json

from vultron.as_vocab.base import activitystreams_object
from vultron.as_vocab.base.objects.base import as_Object


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Document(as_Object):
    """Base class for all ActivityPub documents. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-document>"""


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Image(as_Document):
    """Base class for all ActivityPub images. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-image>"""


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Video(as_Document):
    """Base class for all ActivityPub videos. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-video>"""


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Audio(as_Document):
    """Base class for all ActivityPub audio. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-audio>"""


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Page(as_Document):
    """Base class for all ActivityPub pages. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-page>"""


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Article(as_Document):
    """Base class for all ActivityPub articles. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-article>"""


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Note(as_Object):
    """Base class for all ActivityPub notes. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-note>"""


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Event(as_Object):
    """Base class for all ActivityPub events. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-event>"""


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Profile(as_Object):
    """Base class for all ActivityPub profiles. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-profile>"""

    describes: Optional[Any] = None


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Tombstone(as_Object):
    """Base class for all ActivityPub tombstones. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-tombstone>"""

    former_type: Optional[Any] = None
    deleted: Optional[datetime] = None


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Relationship(as_Object):
    """Base class for all ActivityPub relationships. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-relationship>"""

    subject: Optional[Any] = None
    object: Optional[Any] = None
    relationship: Optional[Any] = None


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Place(as_Object):
    """Base class for all ActivityPub places. See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-place>"""

    longitude: Optional[float] = None
    latitude: Optional[float] = None
    altitude: Optional[float] = None
    radius: Optional[float] = None
    accuracy: Optional[float] = None
    units: Optional[str] = None


def main():
    from vultron.as_vocab.base.utils import print_object_examples

    print_object_examples()


if __name__ == "__main__":
    main()
