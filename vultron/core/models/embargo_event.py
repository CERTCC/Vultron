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

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field
from pydantic.alias_generators import to_camel

from vultron.core.models._helpers import days_from_now_utc, now_utc
from vultron.core.models.base import CoreObject, NonEmptyString


def _45_days_hence() -> datetime:
    """Return a datetime 45 days in the future (UTC)."""
    return days_from_now_utc(45)


class EmbargoEvent(CoreObject):
    """Domain representation of an EmbargoEvent.

    Canonical core type for the Vultron ``EmbargoEvent`` object.
    ``type_`` is ``"EmbargoEvent"`` to match the wire vocabulary key, enabling
    proper DataLayer round-trips via ``dl.read()`` and ``dl.list_objects()``,
    and to auto-register this class in :data:`CORE_VOCABULARY`.
    """

    model_config = ConfigDict(alias_generator=to_camel)

    type_: Literal["EmbargoEvent"] = Field(
        default="EmbargoEvent",
        validation_alias="type",
        serialization_alias="type",
    )
    start_time: datetime = Field(default_factory=now_utc)
    end_time: datetime = Field(default_factory=_45_days_hence)
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]


# Backward-compatibility alias
VultronEmbargoEvent = EmbargoEvent
