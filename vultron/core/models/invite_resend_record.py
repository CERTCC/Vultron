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
"""The CASE_MANAGER's record of its resends of one Invite to one participant.

When a participant states its ledger position, the CASE_MANAGER resends each
Invite the participant still owes an answer to (SYNC-20-001, ADR-0163).  The
resends are rate-bounded per Invite and participant: each one doubles the
cooldown before the next, up to a ceiling (SYNC-20-005).  This record keeps
what that bound needs.

It is not replication state (SYNC-04-001): an inert participant is resent its
Invites too, and SYNC-17-002 records no replication state for it.

Spec: SYNC-20-005.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.base import CoreRecord, NonEmptyString, with_record_id


class InviteResendRecord(CoreRecord):
    """How often, and when last, one Invite was resent to one participant.

    The ``id_`` is derived from ``invite_id`` and ``peer_id``, so the same
    pair always resolves to the same record.

    Attributes:
        invite_id: The id of the Invite resent, as first sent.
        peer_id: The participant actor it was resent to.
        resends: Consecutive resends queued so far; each doubles the cooldown
            before the next (SYNC-20-005).
        last_resent_at: When the last resend was queued.
    """

    type_: Literal["InviteResendRecord"] = Field(  # type: ignore[assignment]
        default="InviteResendRecord",
        validation_alias="type",
        serialization_alias="type",
    )
    invite_id: NonEmptyString
    peer_id: NonEmptyString
    resends: int = Field(default=1, ge=1)
    last_resent_at: datetime

    @classmethod
    def build_id(cls, invite_id: str, peer_id: str) -> str:
        """The record id for the resends of *invite_id* to *peer_id*."""
        return derived_activity_id("invite-resend", invite_id, peer_id)

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Derive ``id_`` from ``invite_id`` and ``peer_id``."""
        if not isinstance(data, dict):
            return data
        invite_id = data.get("invite_id")
        peer_id = data.get("peer_id")
        if invite_id is not None and peer_id is not None:
            data = with_record_id(data, cls.build_id(invite_id, peer_id))
        return data


__all__ = ["InviteResendRecord"]
