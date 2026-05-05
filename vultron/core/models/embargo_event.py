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

"""Domain representation of an EmbargoEvent."""

from datetime import datetime, timedelta, timezone

from pydantic import Field

from vultron.core.models.base import NonEmptyString, VultronObject


def _now_utc() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(tz=timezone.utc)


def _45_days_hence() -> datetime:
    """Return a datetime 45 days in the future (UTC)."""
    return _now_utc() + timedelta(days=45)


class VultronEmbargoEvent(VultronObject):
    """Domain representation of an EmbargoEvent.

    ``type_`` is ``"EmbargoEvent"`` to match the wire vocabulary key, enabling
    proper DataLayer round-trips via ``dl.read()`` and ``dl.list_objects()``.
    """

    type_: str = Field(
        default="EmbargoEvent",
        validation_alias="type",
        serialization_alias="type",
    )
    start_time: datetime = Field(default_factory=_now_utc)
    end_time: datetime = Field(default_factory=_45_days_hence)
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
