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
"""

from __future__ import annotations

import urllib.parse
from typing import Annotated, Any, Literal

from pydantic import Field, StrictInt, model_validator

from vultron.core.models.base import CoreRecord, UriString, with_record_id

#: A ``senderSequence`` or ``expectedSenderSequence``: a positive integer.
SenderSequence = Annotated[StrictInt, Field(gt=0)]


class SenderSequenceCounter(CoreRecord):
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
    case_id: UriString = Field(..., description="URI of the case")
    sender_id: UriString = Field(..., description="URI of the sender")
    last_used: int = Field(
        default=0, ge=0, description="The last number used; 0 before any"
    )

    @classmethod
    def build_id(cls, case_id: str, sender_id: str) -> str:
        """The record id of *sender_id*'s counter for *case_id*."""
        case_slug = urllib.parse.quote(case_id, safe="")
        sender_slug = urllib.parse.quote(sender_id, safe="")
        return f"sender-sequence/{case_slug}/{sender_slug}"

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


__all__ = ["SenderSequence", "SenderSequenceCounter"]
