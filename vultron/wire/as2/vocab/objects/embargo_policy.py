#!/usr/bin/env python
"""
Provides an EmbargoPolicy object for the Vultron ActivityStreams Vocabulary.
"""

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from datetime import timedelta
from typing import Any, TypeAlias, cast

import isodate  # type: ignore[import-untyped]
from pydantic import Field, field_serializer, field_validator

from vultron.core.models.base import NonEmptyString
from vultron.core.models.enums import VultronObjectType as VO_type
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.registry import activitystreams_object
from vultron.wire.as2.vocab.objects.base import VultronObject


def _parse_duration(value: Any) -> timedelta | None:
    """Parse an ISO 8601 duration string or timedelta; reject calendar units."""
    if value is None:
        return None
    if isinstance(value, timedelta):
        return value
    if isinstance(value, str):
        # Reject week designator (W) in date part per DUR-02-002, DUR-04-001.
        # isodate silently converts P2W → timedelta(weeks=2) so we must check
        # explicitly before parsing.
        date_part = value.split("T")[0]
        if "W" in date_part:
            raise ValueError(
                f"Duration must not include weeks (W unit is not allowed"
                f" per DUR-02-002): {value!r}"
            )
        try:
            parsed = isodate.parse_duration(value)
        except Exception as exc:
            raise ValueError(f"Invalid ISO 8601 duration: {value!r}") from exc
        if not isinstance(parsed, timedelta):
            raise ValueError(
                f"Duration must not include years or months (calendar units"
                f" are not allowed): {value!r}"
            )
        return cast(timedelta, parsed)
    raise TypeError(f"Unsupported duration value: {value!r}")


@activitystreams_object
class EmbargoPolicy(VultronObject):
    """
    Represents an Actor's stated embargo preferences.

    Allows actors to declare their default embargo preferences so that
    coordinators can evaluate compatibility before proposing an embargo or
    inviting an actor to a case.

    Fields:
        actor_id: Full URI of the Actor to which the policy applies (required).
        inbox: URL of the Actor's ActivityPub inbox (required).
        preferred_duration: Preferred embargo duration as ISO 8601 duration
            string (e.g. ``"P90D"`` for ninety days) (required).
        minimum_duration: Minimum acceptable duration as ISO 8601 duration
            string; the Actor SHOULD reject embargoes shorter than this value
            (optional).
        maximum_duration: Maximum acceptable duration as ISO 8601 duration
            string; the Actor SHOULD reject embargoes longer than this value
            (optional).
        notes: Free-text description of the Actor's embargo preferences
            (optional).

    Per specs/embargo-policy.md EP-01-001 through EP-01-004 and
    specs/duration.md DUR-01-001, DUR-05-001, DUR-05-002.
    """

    type_: VO_type = Field(
        default=VO_type.EMBARGO_POLICY,
        validation_alias="type",
        serialization_alias="type",
    )

    actor_id: NonEmptyString = Field(
        ...,
        description="Full URI of the Actor to which this policy applies",
    )
    inbox: NonEmptyString = Field(
        ...,
        description="URL of the Actor's ActivityPub inbox",
    )
    preferred_duration: timedelta = Field(
        ...,
        description="Preferred embargo duration as ISO 8601 duration string",
    )
    minimum_duration: timedelta | None = Field(
        default=None,
        description="Minimum acceptable embargo duration as ISO 8601 duration",
    )
    maximum_duration: timedelta | None = Field(
        default=None,
        description="Maximum acceptable embargo duration as ISO 8601 duration",
    )
    notes: NonEmptyString | None = Field(
        default=None,
        description="Free-text description of the Actor's embargo preferences",
    )

    @field_validator(
        "preferred_duration",
        "minimum_duration",
        "maximum_duration",
        mode="before",
    )
    @classmethod
    def _parse_iso8601_duration(cls, value: Any) -> timedelta | None:
        """Accept ISO 8601 duration strings or timedelta; reject calendar units.

        Per specs/duration.md DUR-04-001, DUR-04-002, DUR-05-001.
        """
        return _parse_duration(value)

    @field_serializer(
        "preferred_duration",
        "minimum_duration",
        "maximum_duration",
        when_used="json",
    )
    def _serialize_duration(self, value: timedelta | None) -> str | None:
        """Serialize timedelta to ISO 8601 duration string.

        Per specs/duration.md DUR-05-002.
        """
        if value is None:
            return None
        return cast(str, isodate.duration_isoformat(value))


EmbargoPolicyRef: TypeAlias = ActivityStreamRef[EmbargoPolicy]


def main():
    obj = EmbargoPolicy(
        actor_id="https://example.org/actors/vendor",
        inbox="https://example.org/actors/vendor/inbox",
        preferred_duration=timedelta(days=90),
        minimum_duration=timedelta(days=45),
        maximum_duration=timedelta(days=180),
        notes="Prefer 90 days but consider shorter for critical vulnerabilities.",
    )
    _json = obj.to_json(indent=2)
    print(_json)
    with open("../../../doc/examples/embargo_policy.json", "w") as fp:
        fp.write(_json)


if __name__ == "__main__":
    main()
