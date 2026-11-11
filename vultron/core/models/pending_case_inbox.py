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
"""Per-case bookkeeping for messages waiting on a case replica.

What waits is read from the waiting messages themselves, each of which names
the case it waits on (``ReceivedActivityRecord.awaiting_case_id``, ADR-0154).
This record keeps only what is per case and not per message: the stub
Invite's trust anchor, and ``queued_at``, the one clock that opens the
CBT-03-001 expiry window.
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from vultron.core.models._helpers import timestamp_serializer
from vultron.core.models.base import CoreRecord, UriString, with_record_id


class VultronPendingCaseInbox(CoreRecord):
    """Per-case bookkeeping for a case whose replica is not held yet.

    Tracks when the first activity waiting for this case was queued
    (``queued_at``) so that a bounded expiry window can be enforced
    (CBT-03-001, CBT-03-003).  Which activities wait is not here: each names
    this case on its own ``ReceivedActivityRecord`` (ADR-0154).

    The same record carries the stub Invite's trust anchor (PCR-03-004 path
    b): the CASE_MANAGER the Invite named, in ``case_actor_id``, with
    ``invite_anchored`` set.  An anchored record outlives the expiry of its
    queue, since the anchor is what admits the case's later ``Announce``.
    The anchor is fixed only once the invitee accepts the Invite that set it
    (``invite_accepted``); until then a later stub Invite replaces it.
    """

    type_: Literal["PendingCaseInbox"] = Field(  # type: ignore[assignment]
        default="PendingCaseInbox",
        validation_alias="type",
        serialization_alias="type",
    )
    case_id: UriString = Field(..., description="URI of the pending case")
    # Required: the instant of the act that queued the first activity
    # (ADR-0176).
    queued_at: datetime = Field(
        ...,
        description="UTC timestamp when the first activity was queued for this case",
    )
    _serialize_queued_at = timestamp_serializer("queued_at")
    case_actor_id: UriString | None = Field(
        default=None,
        description=(
            "URI of the CASE_MANAGER a stub Invite named, once "
            "``invite_anchored`` is set (PCR-03-004 path b).  Before that, "
            "the sender of the first pre-bootstrap activity, which admits "
            "no sender."
        ),
    )
    invite_anchored: bool = Field(
        default=False,
        description=(
            "True once a stub Invite recorded ``case_actor_id`` as its trust "
            "anchor (PCR-03-004 path b).  Until then ``case_actor_id`` "
            "admits no sender; queue expiry keeps an anchored record."
        ),
    )
    anchor_invite_id: UriString | None = Field(
        default=None,
        description=(
            "The sender's id for the stub Invite that set the anchor; the "
            "invitee's Accept of that Invite fixes it (PCR-03-004 path b)."
        ),
    )
    invite_accepted: bool = Field(
        default=False,
        description=(
            "True once the invitee sent ``Accept`` for ``anchor_invite_id``.  "
            "Until then a later stub Invite naming another CaseActor replaces "
            "the anchor; after it, such an Invite is refused (PCR-03-009, PCR-03-010)."
        ),
    )

    @classmethod
    def build_id(cls, case_id: str) -> str:
        """Return the stable DataLayer ID for *case_id*."""
        slug = urllib.parse.quote(case_id, safe="")
        return f"pending-case-inbox/{slug}"

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``case_id``."""
        if isinstance(data, dict):
            case_id = data.get("case_id")
            if case_id is not None:
                data = with_record_id(data, cls.build_id(case_id))
        return data
