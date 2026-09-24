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
from typing import Any, ClassVar, TypeAlias, cast

import isodate  # type: ignore[import-untyped]
from pydantic import ConfigDict, field_serializer, field_validator, Field

from vultron.core.models._helpers import as_utc, now_utc
from vultron.core.models.base import VultronObject
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.utils import is_blank
from vultron.wire.as2.vocab.base.links import (
    ActivityStreamRef,
    ActivityStreamRequiredRef,
)


class as_Object(as_Base, VultronObject):
    """Base class for all ActivityPub objects.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#object>
    """

    # Explicitly opt out of validate_assignment here: the wire branch must
    # stay lenient for inbound AS2 data (ARCH-12-002).  VultronObject now
    # carries ValidatedAssignmentMixin, so without this override the flag
    # propagates here via the cross-branch MRO.
    model_config = ConfigDict(validate_assignment=False, frozen=True)

    # Wire-branch types must NOT self-register in CORE_TYPE_MAP (issue #2416).
    # Setting False here propagates to all as_Object subclasses via inheritance,
    # so VultronObject.__init_subclass__ skips them entirely.
    _is_core_branch: ClassVar[bool] = False

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
        return cast(str, isodate.duration_isoformat(value))

    @field_validator("duration", mode="before")
    @classmethod
    def validate_duration(cls, value: Any) -> timedelta | None:
        if value is None:
            return value
        if isinstance(value, timedelta):
            return value
        if isinstance(value, str):
            return cast(timedelta, isodate.parse_duration(value))
        raise TypeError(f"Unsupported duration value: {value!r}")

    @field_serializer(
        "start_time", "end_time", "published", "updated", when_used="json"
    )
    def serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    @field_validator(
        "start_time", "end_time", "published", "updated", mode="before"
    )
    @classmethod
    def validate_datetime(
        cls, value: datetime | str | None
    ) -> datetime | None:
        """Coerce a wire timestamp, reading a blank string as absence.

        One validator covers all four timestamp fields, so the "if present,
        then non-empty" invariant (CS-08-001) is expressed here once rather
        than as four per-field stubs (CS-08-002).  The blank test comes from
        ``vocab.base.utils.is_blank``, the wire layer's single definition of
        blank, shared with ``parser.parse_activity``'s required-field guards
        (CS-22-001).

        A blank string is *absence*, not a malformed value: it carries no time,
        and the alternative — raising — is not available to a nested object.
        ``parser._expand_inline_value`` refuses an inline object that fails its
        own class's validation, so treating a cosmetic blank as a fault would
        reject the whole message over a field the nested object is allowed to
        omit outright.

        Absence here means ``None``, **not** the field default.  ``published``
        and ``updated`` carry ``default_factory=now_utc`` so that an object this
        process *authors* is stamped with the local clock; on inbound data that
        default would fabricate a time and present it as the sender's claim.
        ``as_Base.carry_absent_times_on_inbound`` therefore reads an omitted
        key as ``None`` under the inbound validation context, so omission,
        ``null`` and blank all arrive as the same ``None`` (ISSUE-3257,
        ADR-0103).

        A non-blank string that is not a timestamp stays an error: blank means
        "not provided", and reporting corrupt data as missing data would tell
        the sender to supply a field they already sent (ISSUE-3217).
        """
        if value is None:
            return value
        if isinstance(value, datetime):
            return as_utc(value)
        if isinstance(value, str):
            if is_blank(value):
                return None
            return as_utc(datetime.fromisoformat(value))
        raise TypeError(f"Unsupported datetime value: {value!r}")


as_ObjectRef: TypeAlias = ActivityStreamRef[as_Object] | None
as_ObjectRequiredRef: TypeAlias = ActivityStreamRequiredRef[as_Object]


def main():
    o = as_Object()
    print(o.to_json(indent=2))
    print(o.model_dump(exclude_none=True))


if __name__ == "__main__":
    main()
