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

"""The receiver's archive of one received activity (ADR-0111, CLP-10-017).

Intake writes one :class:`ReceivedActivityRecord` per received activity.  The
record's id is the **receiver's** key, derived by :meth:`build_id` from the
sender's activity id, so the archive never occupies a row under an id the
sender chose: a sender who names its activity after a record the receiver
derives (a pending-case-inbox marker, an offer record, a report-case link)
cannot squat that id ahead of the receiver's own write.  The sender's id is
kept in :attr:`activity_id` for the reverse lookup, and the activity itself is
carried whole in :attr:`activity`, exactly as the event delivered it.

Lookup in both directions:

- their key → ours: ``dl.read(ReceivedActivityRecord.build_id(their_id))``;
- ours → theirs: ``record.activity_id``.
"""

import urllib.parse
from typing import Any, Literal

from pydantic import Field, model_validator

from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import CoreRecord, NonEmptyString, with_record_id


class ReceivedActivityRecord(CoreRecord):
    """One received activity, archived under a key the receiver derives.

    Attributes:
        activity_id: The sender's id for the activity — their key.  The
            record's own ``id_`` is derived from it by :meth:`build_id`.
        activity: The received activity, as the event carried it.
    """

    type_: Literal["ReceivedActivityRecord"] = Field(  # type: ignore[assignment]
        default="ReceivedActivityRecord",
        validation_alias="type",
        serialization_alias="type",
    )
    activity_id: NonEmptyString = Field(
        ..., description="The sender's id for the archived activity"
    )
    activity: VultronActivity = Field(
        ..., description="The received activity, as received"
    )

    @classmethod
    def build_id(cls, activity_id: str) -> str:
        """The receiver's stable DataLayer id for the activity *activity_id*."""
        slug = urllib.parse.quote(activity_id, safe="")
        return f"received-activity/{slug}"

    @classmethod
    def for_activity(
        cls, activity: VultronActivity
    ) -> "ReceivedActivityRecord":
        """The archive record for *activity*."""
        return cls(activity_id=activity.id_, activity=activity)

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``activity_id``."""
        if isinstance(data, dict):
            activity_id = data.get("activity_id")
            if activity_id is not None:
                data = with_record_id(data, cls.build_id(activity_id))
        return data


__all__ = ["ReceivedActivityRecord"]
