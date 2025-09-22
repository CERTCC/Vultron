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
from typing import TypeAlias, Any

from pydantic import Field, field_serializer, field_validator, model_validator

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

    start_time: datetime | None = Field(
        default_factory=now_utc, json_schema_extra={"format": "date-time"}
    )
    end_time: datetime | None = Field(
        default_factory=_45_days_hence,
        json_schema_extra={"format": "date-time"},
    )

    @field_serializer("start_time", "end_time", when_used="json")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return to_isofmt(value)

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def validate_datetime(cls, value: Any) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return from_isofmt(value)
        return value

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
