#!/usr/bin/env python
"""This module provides base activity classes"""
#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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

from typing import Literal

from pydantic import Field

from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.actors import as_ActorRef
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.base.registry import activitystreams_activity


@activitystreams_activity
class as_Activity(as_Object):
    """https://www.w3.org/TR/activitystreams-vocabulary/#dfn-activity
    An Activity is a subtype of Object that describes some form of action that may happen, is
    currently happening, or has already happened. The Activity type itself serves as an abstract
    base type for all types of activities. It is important to note that an Activity is not a
    representation of a currently executing process, but rather a statement about that process.
    For example, a person walking down the street is not an Activity unless they are posting a
    picture of themselves walking down the street. The Activity in that case would be the posting
    of the picture, not the person walking down the street.
    """

    as_type: Literal["Activity"] = Field(default="Activity", alias="type")

    actor: as_ActorRef
    target: as_Object | as_Link | str | None = None
    origin: as_Object | as_Link | str | None = None
    instrument: as_Object | as_Link | str | None = None
    result: as_Object | as_Link | str | None = None

    def description(self):
        raise NotImplementedError


def main():
    x = as_Activity()
    print(x.to_json(indent=2))


if __name__ == "__main__":
    main()
