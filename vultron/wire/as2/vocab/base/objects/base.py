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

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, TypeAlias, cast

import isodate  # type: ignore[import-untyped]
from pydantic import ConfigDict, Field, field_serializer, field_validator

from vultron.core.models._helpers import as_utc, format_timestamp
from vultron.core.models.base import (
    CoreObject,
    LanguageMap,
    language_map_field,
)
from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.links import (
    ActivityStreamRef,
    ActivityStreamRequiredRef,
    as_Link,
)
from vultron.wire.as2.vocab.base.utils import is_blank


class as_Object(as_Base):
    """Base class for all ActivityPub objects.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#object>
    """

    model_config = ConfigDict(frozen=True)

    # The AS2 reference properties (AS2 Vocabulary section 4).  Each holds an
    # embedded object, a Link or an IRI, and every one but ``replies`` may hold
    # a list of them.  Inbound leniency means accepting each shape AS2 allows,
    # never a blank: the IRI branch is ``NonEmptyString``, so ``""`` and
    # whitespace are refused at the parse edge (CS-08-001, #3894).  The
    # aliases are declared below the class because they name it.
    replies: as_CollectionValue = None
    url: as_UrlValues = None
    generator: as_ObjectOrLinkValues = None
    context: as_ObjectOrLinkValues = None
    tag: as_ObjectOrLinkValues = None
    in_reply_to: as_ObjectOrLinkValues = None

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
    # Required, with no default (ADR-0176): an outbound object states the
    # act's instant, and a received omission is read as ``None``
    # (``as_Base.carry_absent_times_on_inbound``).
    published: datetime | None = Field(
        json_schema_extra={"format": "date-time"}
    )
    updated: datetime | None = Field(json_schema_extra={"format": "date-time"})

    # content: blank text is refused when the object is built (CS-08-001,
    # VM-07-005)
    content: NonEmptyString | None = None
    summary: NonEmptyString | None = None
    icon: as_ObjectOrLinkValues = None
    image: as_ObjectOrLinkValues = None
    attachment: as_ObjectOrLinkValues = None
    location: as_ObjectOrLinkValues = None
    to: as_ObjectOrLinkValues = None
    cc: as_ObjectOrLinkValues = None
    bto: as_ObjectOrLinkValues = None
    bcc: as_ObjectOrLinkValues = None
    audience: as_ObjectOrLinkValues = None
    attributed_to: as_ObjectOrLinkValues = None
    # The natural-language map forms (AS2 Core section 4.7), declared on
    # ``CoreObject`` too (ARCH-25-008).  Empty by default and left out of a
    # dump when empty.
    content_map: LanguageMap = language_map_field()
    name_map: LanguageMap = language_map_field()
    summary_map: LanguageMap = language_map_field()

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
        return format_timestamp(value)

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

        Absence here means ``None``.  ``published`` and ``updated`` are
        required, with no default (ADR-0176): an object this process
        *authors* states the act's instant, and a received one carries the
        sender's claim.  ``as_Base.carry_absent_times_on_inbound`` reads an omitted
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


as_ObjectRef: TypeAlias = ActivityStreamRef[as_Object] | CoreObject | None
as_ObjectRequiredRef: TypeAlias = (
    ActivityStreamRequiredRef[as_Object] | CoreObject
)

#: One value of an AS2 property whose range is ``Object | Link``: an embedded
#: wire object, a core object (a domain type is its own wire form, ADR-0099),
#: a Link, or a non-blank IRI.  ``icon`` and ``image`` use it too: their
#: ``Image`` range is an ``as_Object`` subclass this module cannot import.
as_ObjectOrLink: TypeAlias = as_Object | CoreObject | as_Link | NonEmptyString

#: A non-functional ``Object | Link`` property: one value or a list of them.
#: ``Sequence`` rather than ``list`` so a ``list[str]`` of actor ids is a valid
#: argument: ``list`` is invariant in its item type.
#: The list branch also keeps these slots out of the dehydrated reference set,
#: which matches the single-valued ``as_ObjectRef`` shape only (ARCH-23-004).
as_ObjectOrLinkValues: TypeAlias = (
    as_ObjectOrLink | Sequence[as_ObjectOrLink] | None
)

#: ``url``: an ``xsd:anyURI`` or a Link, one or many; never an object.
as_UrlValues: TypeAlias = (
    as_Link | NonEmptyString | Sequence[as_Link | NonEmptyString] | None
)

#: ``replies``: a functional property whose range is ``Collection``, an
#: ``as_Object`` subclass this module cannot import; or the collection's IRI.
as_CollectionValue: TypeAlias = as_Object | CoreObject | NonEmptyString | None

# The fields above name these aliases, which name the class, so the schema is
# completed here, before any subclass is declared.
as_Object.model_rebuild()


def main():
    o = as_Object(published=None, updated=None)
    print(o.to_json(indent=2))
    print(o.model_dump(exclude_none=True))


if __name__ == "__main__":
    main()
