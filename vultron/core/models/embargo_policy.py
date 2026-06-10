#!/usr/bin/env python

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

"""Domain representation of an EmbargoPolicy."""

from datetime import timedelta
from typing import Any, Literal, cast

import isodate  # type: ignore[import-untyped]
from pydantic import Field, field_serializer, field_validator

from vultron.core.models.base import CoreObject, NonEmptyString


def parse_duration(value: Any) -> timedelta | None:
    """Parse an ISO 8601 duration string or timedelta; reject calendar units.

    Per specs/duration.yaml DUR-04-001, DUR-04-002, DUR-05-001.
    """
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


class EmbargoPolicy(CoreObject):
    """Domain representation of an EmbargoPolicy.

    Canonical core type for the Vultron ``EmbargoPolicy`` object.
    ``type_`` is ``"EmbargoPolicy"`` to auto-register this class in
    :data:`CORE_VOCABULARY`.

    Allows actors to declare their default embargo preferences so that
    coordinators can evaluate compatibility before proposing an embargo or
    inviting an actor to a case.

    Fields:
        actor_id: Full URI of the Actor to which the policy applies (required).
        inbox: URL of the Actor's ActivityPub inbox (required).
        preferred_duration: Preferred embargo duration as a
            :class:`~datetime.timedelta` (required).
        minimum_duration: Minimum acceptable duration; the Actor SHOULD reject
            embargoes shorter than this value (optional).
        maximum_duration: Maximum acceptable duration; the Actor SHOULD reject
            embargoes longer than this value (optional).
        notes: Free-text description of the Actor's embargo preferences
            (optional).

    Per specs/embargo-policy.yaml EP-01-001 through EP-01-004 and
    specs/duration.yaml DUR-01-001, DUR-05-001, DUR-05-002.
    """

    type_: Literal["EmbargoPolicy"] = Field(
        default="EmbargoPolicy",
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
        description="Preferred embargo duration",
    )
    minimum_duration: timedelta | None = Field(
        default=None,
        description="Minimum acceptable embargo duration",
    )
    maximum_duration: timedelta | None = Field(
        default=None,
        description="Maximum acceptable embargo duration",
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

        Per specs/duration.yaml DUR-04-001, DUR-04-002, DUR-05-001.
        """
        return parse_duration(value)

    @field_serializer(
        "preferred_duration",
        "minimum_duration",
        "maximum_duration",
        when_used="json",
    )
    def _serialize_duration(self, value: timedelta | None) -> str | None:
        """Serialize timedelta to ISO 8601 duration string.

        Per specs/duration.yaml DUR-05-002.
        """
        if value is None:
            return None
        return cast(str, isodate.duration_isoformat(value))
