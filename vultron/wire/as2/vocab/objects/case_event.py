#!/usr/bin/env python
"""
Provides a CaseEvent model for trusted-timestamp event logging on VulnerabilityCase objects.
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

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer, field_validator

from vultron.core.models.base import NonEmptyString
from vultron.wire.as2.vocab.base.dt_utils import now_utc


def _now_utc() -> datetime:
    return now_utc()


class CaseEvent(BaseModel):
    """Append-only event log entry for a VulnerabilityCase.

    Records a state-changing event with a server-generated trusted timestamp
    at the time of receipt.  The CaseActor is the sole trusted source of
    event ordering within a case; ``received_at`` MUST be set by the handler
    at time of receipt, never copied from an incoming activity payload.

    Fields:
        object_id: Full URI of the object being acted upon.
        event_type: Short descriptor of the event kind
            (e.g. ``"embargo_accepted"``, ``"participant_joined"``).
        received_at: Server-generated TZ-aware UTC timestamp set at receipt;
            defaults to the current UTC time.

    Per specs/case-management.md CM-02-009, CM-10-002;
    plan/IMPLEMENTATION_PLAN.md SC-PRE-1.
    """

    object_id: NonEmptyString = Field(
        ...,
        description="Full URI of the object being acted upon",
    )
    event_type: NonEmptyString = Field(
        ...,
        description="Short descriptor of the event kind",
    )
    received_at: datetime = Field(
        default_factory=_now_utc,
        description="Server-generated TZ-aware UTC timestamp set at receipt",
    )

    @field_validator("received_at", mode="before")
    @classmethod
    def parse_received_at(cls, v) -> datetime:
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    @field_serializer("received_at", when_used="json")
    def serialize_received_at(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
