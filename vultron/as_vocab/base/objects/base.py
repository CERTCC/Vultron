#!/usr/bin/env python
"""file: base
author: adh
created_at: 2/15/23 2:01 PM
"""
#  Copyright (c) 2023-2024 Carnegie Mellon University and Contributors.
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
from datetime import datetime, timedelta
from typing import Any, List, Optional

from dataclasses_json import LetterCase, config, dataclass_json
from marshmallow import fields

from vultron.as_vocab.base.base import as_Base
from vultron.as_vocab.base.dt_utils import (
    from_isofmt,
    now_utc,
    to_isofmt,
)
from vultron.as_vocab.base.utils import exclude_if_none


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Object(as_Base):
    """Base class for all ActivityPub objects.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#object>
    """

    replies: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    url: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    generator: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    context: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    tag: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    in_reply_to: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )

    # time (aka Wibbly-Wobbly Time-Wimey Stuff)
    duration: Optional[timedelta] = field(
        metadata=config(
            exclude=exclude_if_none,
            encoder=to_isofmt,
            decoder=from_isofmt,
            mm_field=fields.TimeDelta(
                precision="seconds", serialization_type=int, allow_none=True
            ),
        ),
        default=None,
    )
    start_time: Optional[datetime] = field(
        metadata=config(
            exclude=exclude_if_none,
            encoder=to_isofmt,
            decoder=from_isofmt,
            mm_field=fields.DateTime(format="iso", allow_none=True),
        ),
        default=None,
    )
    end_time: Optional[datetime] = field(
        metadata=config(
            exclude=exclude_if_none,
            encoder=to_isofmt,
            decoder=from_isofmt,
            mm_field=fields.DateTime(format="iso", allow_none=True),
        ),
        default=None,
    )
    published: Optional[datetime] = field(
        metadata=config(
            exclude=exclude_if_none,
            encoder=to_isofmt,
            decoder=from_isofmt,
            mm_field=fields.DateTime(format="iso", allow_none=True),
        ),
        default_factory=now_utc,
    )
    updated: Optional[datetime] = field(
        metadata=config(
            exclude=exclude_if_none,
            encoder=to_isofmt,
            decoder=from_isofmt,
            mm_field=fields.DateTime(format="iso", allow_none=True),
        ),
        default_factory=now_utc,
    )

    # content
    content: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    summary: Optional[str] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    icon: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    image: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    attachment: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )

    # location
    location: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )

    # addressing
    to: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    cc: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )

    bto: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    bcc: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )

    audience: Optional[Any] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )

    # Todo: replace camelCase with snake_case
    attributed_to: Optional[List[Any]] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )


def main():
    o = as_Object()
    print(o.to_json(indent=2))


if __name__ == "__main__":
    main()
