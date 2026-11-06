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

"""A participant's sender sequence for a case (SYNC-21, ADR-0178).

Each participant numbers the case activities it sends the CASE_MANAGER with
a counter kept per (sender, case): the first is 1, each next one is one more
than the last (SYNC-21-001, SYNC-21-002).  The number travels as the
activity's ``senderSequence``; a refusal notice for a number names the next
one the CASE_MANAGER expects as ``expectedSenderSequence`` (SYNC-21-015).

:data:`SenderSequence` is the value both carry: a positive integer, strict,
so a number spelled as text or a boolean is no number.  The counter itself
is :class:`SenderSequenceCounter`, one stored record per (sender, case) in
the sender's own DataLayer (SYNC-21-020), so the numbering survives a
restart.

The CASE_MANAGER's side is :class:`SenderSequenceOrder`, one stored record per
(sender, case) in the CASE_MANAGER's DataLayer: the next number it expects
from the sender and the activities it holds past a gap (SYNC-21-009,
SYNC-21-010, SYNC-21-020).  The held bodies themselves stay on each
activity's one ``ReceivedActivityRecord`` (IO-03-009); this record is only
the index that finds them, as ``HeldLedgerAnnounce`` is for a held ledger
entry.
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime
from typing import Annotated, Any, ClassVar, Literal

from pydantic import (
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from vultron.core.models._helpers import as_utc, timestamp_serializer
from vultron.core.models.base import (
    CoreRecord,
    NonEmptyString,
    UriString,
    ValidatedAssignmentMixin,
    with_record_id,
)
from vultron.primitives import normalise_actor_id

#: A ``senderSequence`` or ``expectedSenderSequence``: a positive integer.
SenderSequence = Annotated[StrictInt, Field(gt=0)]


def is_sender_sequence(value: object) -> bool:
    """Whether *value* is a valid :data:`SenderSequence`.

    A positive integer, strictly: a boolean or a numeral spelled as text is
    no number.
    """
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


class _PerSenderCaseKey:
    """The id of a record kept per (sender, case), derived from the two.

    A plain mixin, not a record of its own: each record class declares its
    ``case_id`` and ``sender_id`` fields and its ``_ID_PREFIX``.
    """

    _ID_PREFIX: ClassVar[str]

    @classmethod
    def build_id(cls, case_id: str, sender_id: str) -> str:
        """The record id of *sender_id*'s record for *case_id*.

        The sender is keyed by its canonical spelling, so ``…/vendor/`` and
        ``…/vendor`` share one record (OID-01-006).
        """
        case_slug = urllib.parse.quote(case_id, safe="")
        sender_slug = urllib.parse.quote(
            normalise_actor_id(sender_id), safe=""
        )
        return f"{cls._ID_PREFIX}/{case_slug}/{sender_slug}"

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from the case and sender."""
        if isinstance(data, dict):
            case_id = data.get("case_id")
            sender_id = data.get("sender_id")
            if case_id is not None and sender_id is not None:
                data = with_record_id(data, cls.build_id(case_id, sender_id))
        return data


class SenderSequenceCounter(_PerSenderCaseKey, CoreRecord):
    """The last ``senderSequence`` a sender used for a case (SYNC-21-020).

    Attributes:
        case_id: The case the numbers are for.
        sender_id: The participant that numbers its activities.
        last_used: The last number it used; 0 before its first.
    """

    type_: Literal["SenderSequenceCounter"] = Field(  # type: ignore[assignment]
        default="SenderSequenceCounter",
        validation_alias="type",
        serialization_alias="type",
    )
    _ID_PREFIX: ClassVar[str] = "sender-sequence"

    case_id: UriString = Field(..., description="URI of the case")
    sender_id: UriString = Field(..., description="URI of the sender")
    last_used: int = Field(
        default=0, ge=0, description="The last number used; 0 before any"
    )


class HeldSenderActivity(ValidatedAssignmentMixin):
    """One activity the CASE_MANAGER holds past a gap in its sender's numbers.

    Attributes:
        number: The activity's ``senderSequence``.
        activity_id: The sender's id for the activity; its received body is
            held on the ``ReceivedActivityRecord`` of that id (IO-03-009).
        held_at: When the CASE_MANAGER held it, by its own clock; the hold's
            wait runs from the oldest one (SYNC-21-011).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: SenderSequence
    activity_id: NonEmptyString
    held_at: datetime
    _serialize_held_at = timestamp_serializer("held_at")

    @field_validator("held_at")
    @classmethod
    def _held_at_is_utc(cls, value: datetime) -> datetime:
        return as_utc(value)


class SenderSequenceOrder(_PerSenderCaseKey, CoreRecord):
    """The CASE_MANAGER's order of one sender's activities on a case (SYNC-21).

    Attributes:
        case_id: The case the numbers are for.
        sender_id: The participant that numbers its activities.
        next_expected: The number the CASE_MANAGER judges next: one more than
            the highest it judged or skipped (SYNC-21-009).
        skip_through: The highest number of a hold that ended with numbers
            still missing, 0 when none has: every held activity up to it is
            judged in number order, skipping the gaps before it
            (SYNC-21-013).
        last_judged_id: The id of the activity last judged in order, so its
            redelivery is judged again rather than refused as late, as a
            redelivery after a failed act is (ADR-0151).
        held: The activities held past a gap, in number order (SYNC-21-010).
    """

    type_: Literal["SenderSequenceOrder"] = Field(  # type: ignore[assignment]
        default="SenderSequenceOrder",
        validation_alias="type",
        serialization_alias="type",
    )
    _ID_PREFIX: ClassVar[str] = "sender-sequence-order"

    case_id: UriString = Field(..., description="URI of the case")
    sender_id: UriString = Field(..., description="URI of the sender")
    next_expected: int = Field(
        ..., ge=1, description="The number judged next from the sender"
    )
    skip_through: int = Field(
        default=0,
        ge=0,
        description="The highest number of an ended hold; 0 when none",
    )
    last_judged_id: NonEmptyString | None = Field(
        default=None, description="The activity last judged in order"
    )
    held: list[HeldSenderActivity] = Field(
        default_factory=list, description="Activities held past a gap"
    )


__all__ = [
    "HeldSenderActivity",
    "SenderSequence",
    "SenderSequenceCounter",
    "SenderSequenceOrder",
    "is_sender_sequence",
]
