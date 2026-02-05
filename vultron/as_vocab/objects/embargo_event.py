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

# TODO: convert to pydantic idioms
from datetime import datetime, timedelta
from typing import TypeAlias

from pydantic import Field, model_validator

from vultron.as_vocab.base.dt_utils import (
    now_utc,
)
from vultron.as_vocab.base.links import ActivityStreamRef
from vultron.as_vocab.base.objects.object_types import as_Event
from vultron.as_vocab.base.registry import activitystreams_object
from vultron.as_vocab.base.utils import name_of


def _45_days_hence():
    now = now_utc()
    return now + timedelta(days=45)


@activitystreams_object
class EmbargoEvent(as_Event):
    """
    An EmbargoEvent is an Event that represents an embargo on a VulnerabilityCase.
    """

    # note: embargo events don't need to be their own as_type, the value inherited from as_Event is sufficient

    start_time: datetime = Field(
        default_factory=now_utc, json_schema_extra={"format": "date-time"}
    )
    end_time: datetime = Field(
        default_factory=_45_days_hence,
        json_schema_extra={"format": "date-time"},
    )

    # we don't need separate validators for start_time and end_time
    # because the base class validator will be called for both fields

    @model_validator(mode="after")
    def set_name(self):
        start_iso = self.start_time.isoformat()
        end_iso = self.end_time.isoformat()

        parts = [
            "Embargo for",
            name_of(self.context),
        ]
        if self.start_time:
            parts.append(f"start: {start_iso}")
        if self.end_time:
            parts.append(f"end: {end_iso}")
        self.name = " ".join([str(part) for part in parts])
        return self


EmbargoEventRef: TypeAlias = ActivityStreamRef[EmbargoEvent]


def main():
    obj = EmbargoEvent()
    print(obj.to_json(indent=2))


if __name__ == "__main__":
    main()
