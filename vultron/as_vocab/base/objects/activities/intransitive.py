#!/usr/bin/env python
"""file: intransitive
author: adh
created_at: 12/8/22 4:04 PM
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

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Union

from dataclasses_json import LetterCase, config, dataclass_json

from vultron.as_vocab.base import activitystreams_activity
from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.activities.base import (
    as_Activity as Activity,
)
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.base.utils import exclude_if_none


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_IntransitiveActivity(Activity):
    """Base class for all ActivityPub intransitive activities.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#intransitiveactivity>
    """

    def description(self):
        return (
            f"{self.actor} {self.as_type} to {self.target} with {self.result}"
        )


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Travel(as_IntransitiveActivity):
    """The actor travels from the origin to the target.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-travel>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Arrive(as_IntransitiveActivity):
    """The actor arrives at the target. The origin can be used to specify the previous location from which the actor arrived.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-arrive>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Question(as_IntransitiveActivity):
    """The actor poses a question to the target. The origin can be used to specify the context from which the question was posed.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-question>
    """

    anyOf: Optional[as_Object | as_Link | str] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    oneOf: Optional[as_Object | as_Link | str] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    closed: Optional[Union[as_Object, as_Link, datetime, bool]] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )


def main():
    from vultron.as_vocab.base.utils import print_activity_examples

    print_activity_examples()


if __name__ == "__main__":
    main()
