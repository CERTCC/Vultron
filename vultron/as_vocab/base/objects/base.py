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

from datetime import datetime, timedelta
from typing import Any, TypeAlias

import isodate
from pydantic import field_serializer, field_validator, Field

from vultron.as_vocab.base.base import as_Base
from vultron.as_vocab.base.dt_utils import (
    now_utc,
)
from vultron.as_vocab.base.links import ActivityStreamRef


class as_Object(as_Base):
    """Base class for all ActivityPub objects.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#object>
    """

    replies: Any | None = None
    url: Any | None = None
    generator: Any | None = None
    context: Any | None = None
    tag: Any | None = None
    in_reply_to: Any | None = None

    # time (aka Wibbly-Wobbly Time-Wimey Stuff)
    # in python we want datetime or timedelta objects
    # but in json we want iso8601 strings
    # see also serializers and validators below
    duration: timedelta | None = Field(
        default=None, json_schema_extra={"format": "duration"}
    )
    start_time: datetime | None = Field(
        default=None, json_schema_extra={"format": "date-time"}
    )
    end_time: datetime | None = Field(
        default=None, json_schema_extra={"format": "date-time"}
    )
    published: datetime | None = Field(
        default_factory=now_utc, json_schema_extra={"format": "date-time"}
    )
    updated: datetime | None = Field(
        default_factory=now_utc, json_schema_extra={"format": "date-time"}
    )

    # content
    content: Any | None = None
    summary: Any | None = None
    icon: Any | None = None
    image: Any | None = None
    attachment: Any | None = None
    location: Any | None = None
    to: Any | None = None
    cc: Any | None = None
    bto: Any | None = None
    bcc: Any | None = None
    audience: Any | None = None
    attributed_to: Any | None = None

    @field_serializer("duration", when_used="json")
    def serialize_duration(self, value: timedelta | None) -> str | None:
        if value is None:
            return None
        return isodate.duration_isoformat(value)

    @field_validator("duration", mode="before")
    @classmethod
    def validate_duration(cls, value: Any) -> timedelta | None:
        if value is None:
            return value
        if isinstance(value, timedelta):
            return value
        if isinstance(value, str):
            return isodate.parse_duration(value)
        return value

    @field_serializer(
        "start_time", "end_time", "published", "updated", when_used="json"
    )
    def serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return value
        return datetime.isoformat(value)

    @field_validator(
        "start_time", "end_time", "published", "updated", mode="before"
    )
    @classmethod
    def validate_datetime(
        cls, value: datetime | str | None
    ) -> datetime | None:
        if value is None:
            return value
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)


as_ObjectRef: TypeAlias = ActivityStreamRef[as_Object]


def main():
    o = as_Object()
    print(o.to_json(indent=2))
    print(o.model_dump(exclude_none=True))


if __name__ == "__main__":
    main()
