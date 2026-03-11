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

from typing import TypeAlias

from pydantic import Field

from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.registry import activitystreams_object
from vultron.wire.as2.vocab.base.types import (
    NonEmptyString,
    OptionalNonEmptyString,
)
from vultron.wire.as2.vocab.objects.base import VultronObject
from vultron.core.models.enums import VultronObjectType as VO_type


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
        preferred_duration_days: Preferred embargo duration in days (required).
        minimum_duration_days: Minimum acceptable duration; actor SHOULD
            reject embargoes shorter than this value (optional).
        maximum_duration_days: Maximum acceptable duration; actor SHOULD
            reject embargoes longer than this value (optional).
        notes: Free-text description of the Actor's embargo preferences
            (optional).

    Per specs/embargo-policy.md EP-01-001 through EP-01-004.
    """

    as_type: VO_type = Field(default=VO_type.EMBARGO_POLICY, alias="type")

    actor_id: NonEmptyString = Field(
        ...,
        description="Full URI of the Actor to which this policy applies",
    )
    inbox: NonEmptyString = Field(
        ...,
        description="URL of the Actor's ActivityPub inbox",
    )
    preferred_duration_days: int = Field(
        ...,
        description="Preferred embargo duration in days",
        ge=0,
    )
    minimum_duration_days: int | None = Field(
        default=None,
        description="Minimum acceptable embargo duration in days",
        ge=0,
    )
    maximum_duration_days: int | None = Field(
        default=None,
        description="Maximum acceptable embargo duration in days",
        ge=0,
    )
    notes: OptionalNonEmptyString = Field(
        default=None,
        description="Free-text description of the Actor's embargo preferences",
    )


EmbargoPolicyRef: TypeAlias = ActivityStreamRef[EmbargoPolicy]


def main():
    obj = EmbargoPolicy(
        actor_id="https://example.org/actors/vendor",
        inbox="https://example.org/actors/vendor/inbox",
        preferred_duration_days=90,
        minimum_duration_days=45,
        maximum_duration_days=180,
        notes="Prefer 90 days but consider shorter for critical vulnerabilities.",
    )
    _json = obj.to_json(indent=2)
    print(_json)
    with open("../../../doc/examples/embargo_policy.json", "w") as fp:
        fp.write(_json)


if __name__ == "__main__":
    main()
