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
"""When a participant last asked for a case it does not hold (SYNC-15-021).

A participant that receives an ``Announce(CaseLedgerEntry)`` for a case it
does not hold yet holds the ``Announce`` (SYNC-15-004) and asks the
CASE_MANAGER for the case and its whole ledger with a genesis Reject: a
``Reject(CaseLedgerEntry)`` with ``last_accepted_hash=""`` (SYNC-15-001).  One
such Reject asks for everything, so the participant sends one per case per
interval, not one per held entry (SYNC-15-016, SYNC-15-020).  This record
keeps the time it last sent one, in the participant's own store, so the limit
holds across a restart.  The participant deletes it when it seeds the case
(SYNC-15-023).

It is not replication state (SYNC-04-001): that is the CASE_MANAGER's record
of a peer, and this is a participant's record of its own request.

Spec: SYNC-15-016, SYNC-15-021, SYNC-15-023.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from vultron.core.models._helpers import timestamp_serializer
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.base import CoreRecord, UriString, with_record_id


class GenesisRejectRecord(CoreRecord):
    """When this participant last sent a genesis Reject for one case.

    The ``id_`` is derived from ``case_id``, so a case always resolves to the
    same record.

    Attributes:
        case_id: The case the participant does not hold and asked for.
        last_sent_at: When the participant last queued a genesis Reject for
            the case.
    """

    type_: Literal["GenesisRejectRecord"] = Field(  # type: ignore[assignment]
        default="GenesisRejectRecord",
        validation_alias="type",
        serialization_alias="type",
    )
    case_id: UriString = Field(..., description="URI of the missing case")
    last_sent_at: datetime = Field(
        ..., description="When the last genesis Reject for the case was queued"
    )
    _serialize_last_sent_at = timestamp_serializer("last_sent_at")

    @classmethod
    def build_id(cls, case_id: str) -> str:
        """The record id for the genesis Rejects sent for *case_id*."""
        return derived_activity_id("genesis-reject-record", case_id)

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Derive ``id_`` from ``case_id``."""
        if not isinstance(data, dict):
            return data
        case_id = data.get("case_id")
        if case_id is not None:
            data = with_record_id(data, cls.build_id(case_id))
        return data


__all__ = ["GenesisRejectRecord"]
