#!/usr/bin/env python
"""This module provides
# TODO replace me
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
from typing import Optional

from dataclasses_json import config, dataclass_json

from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.base.utils import exclude_if_none


@dataclass_json
@dataclass
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

    actor: as_Object | as_Link | str = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    target: Optional[as_Object | as_Link | str] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    origin: Optional[as_Object | as_Link | str] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    instrument: Optional[as_Object | as_Link | str] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    result: Optional[as_Object | as_Link | str] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )

    def description(self):
        raise NotImplementedError


def main():
    x = as_Activity()
    print(x.to_json(indent=2))


if __name__ == "__main__":
    main()
