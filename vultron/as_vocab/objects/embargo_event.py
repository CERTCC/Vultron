#!/usr/bin/env python
"""
Provides an EmbargoEvent object for the Vultron ActivityStreams Vocabulary.
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
from datetime import datetime, timedelta
from typing import Optional

from dataclasses_json import config
from marshmallow import fields

from vultron.as_vocab.base import activitystreams_object
from vultron.as_vocab.base.dt_utils import (
    from_isofmt,
    now_utc,
    to_isofmt,
)
from vultron.as_vocab.base.objects.object_types import as_Event
from vultron.as_vocab.base.utils import exclude_if_none, name_of


def _45_days_hence():
    now = now_utc()
    return now + timedelta(days=45)


@activitystreams_object
@dataclass(kw_only=True)
class EmbargoEvent(as_Event):
    """
    An EmbargoEvent is an Event that represents an embargo on a VulnerabilityCase.
    """

    start_time: Optional[datetime] = field(
        metadata=config(
            exclude=exclude_if_none,
            encoder=to_isofmt,
            decoder=from_isofmt,
            mm_field=fields.DateTime(format="iso"),
        ),
        default_factory=now_utc,
    )
    end_time: Optional[datetime] = field(
        metadata=config(
            exclude=exclude_if_none,
            encoder=to_isofmt,
            decoder=from_isofmt,
            mm_field=fields.DateTime(format="iso"),
        ),
        default_factory=_45_days_hence,
    )

    def __post_init__(self):
        super().__post_init__()
        start_iso = self.start_time.isoformat()
        end_iso = self.end_time.isoformat()

        # self.as_id = "_".join([start_iso, end_iso])

        parts = [
            "Embargo for",
            name_of(self.context),
        ]
        if self.start_time:
            parts.append(f"start: {start_iso}")
        if self.end_time:
            parts.append(f"end: {end_iso}")
        self.name = " ".join([str(part) for part in parts])


def main():
    obj = EmbargoEvent()
    print(obj.to_json(indent=2))


if __name__ == "__main__":
    main()
