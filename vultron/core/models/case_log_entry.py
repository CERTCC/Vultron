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
"""Core domain model for a canonical case log entry (SYNC-2).

:class:`VultronCaseLogEntry` is the authoritative domain representation of a
single hash-chained log entry used for replication via
``Announce(CaseLogEntry)`` activities.

It extends :class:`~vultron.core.models.base.VultronObject` so that it can be
placed in :attr:`~vultron.core.models.events.base.VultronEvent.object_` and
used by :class:`~vultron.core.use_cases.received.sync.AnnounceLogEntryReceivedUseCase`.

The wire-layer module ``vultron.wire.as2.vocab.objects.case_log_entry``
re-exports this class and registers it in the wire vocabulary under the
``"CaseLogEntry"`` key so that DataLayer round-trips work correctly.

Spec: SYNC-01-002, SYNC-02-003, SYNC-03-001 through SYNC-03-003.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypeAlias

from pydantic import Field, model_validator

from vultron.core.models._helpers import _now_utc
from vultron.core.models.base import VultronObject
from vultron.core.models.case_log import GENESIS_HASH


class VultronCaseLogEntry(VultronObject):
    """Core domain model for a single canonical case log entry.

    The ``id_`` is auto-computed as ``{case_id}/log/{log_index}`` when not
    explicitly provided.

    Fields:
        case_id: URI of the parent :class:`VulnerabilityCase`.
        log_index: Monotonically increasing index scoped to ``case_id``.
        disposition: ``"recorded"`` or ``"rejected"``.
        term: Raft cluster term; ``None`` for single-node deployments.
        log_object_id: Full URI of the asserted activity or primary object.
        event_type: Short machine-readable event descriptor.
        payload_snapshot: Normalised activity payload snapshot.
        prev_log_hash: SHA-256 hash of the previous recorded entry.
        entry_hash: SHA-256 hash of this entry's canonical content.
        received_at: Server-generated TZ-aware UTC receipt timestamp.
        reason_code: Machine-readable rejection reason (rejected entries only).
        reason_detail: Human-readable rejection reason detail.

    Spec: SYNC-01-002, SYNC-02-003, SYNC-03-001 through SYNC-03-003.
    """

    type_: Literal["CaseLogEntry"] = Field(  # type: ignore[assignment]
        default="CaseLogEntry",
        validation_alias="type",
        serialization_alias="type",
    )
    case_id: str = Field(
        ..., description="URI of the parent VulnerabilityCase"
    )
    log_index: int = Field(
        default=-1,
        description="Monotonically increasing index scoped to case_id",
        ge=-1,
    )
    disposition: str = Field(
        default="recorded",
        description="Outcome: 'recorded' or 'rejected'",
    )
    term: int | None = Field(
        default=None,
        description="Raft cluster term; None for single-node deployments",
    )
    log_object_id: str = Field(
        ...,
        description="Full URI of the asserted activity or primary object",
        validation_alias="logObjectId",
        serialization_alias="logObjectId",
    )
    event_type: str = Field(
        ...,
        description="Short machine-readable event descriptor",
        validation_alias="eventType",
        serialization_alias="eventType",
    )
    payload_snapshot: dict[str, Any] = Field(
        default_factory=dict,
        description="Normalised snapshot of the asserted activity payload",
        validation_alias="payloadSnapshot",
        serialization_alias="payloadSnapshot",
    )
    prev_log_hash: str = Field(
        default=GENESIS_HASH,
        description="SHA-256 hex hash of the previous recorded entry",
        validation_alias="prevLogHash",
        serialization_alias="prevLogHash",
    )
    entry_hash: str = Field(
        default="",
        description="SHA-256 hex hash of this entry's canonical content",
        validation_alias="entryHash",
        serialization_alias="entryHash",
    )
    received_at: datetime = Field(
        default_factory=_now_utc,
        description="Server-generated TZ-aware UTC receipt timestamp",
        validation_alias="receivedAt",
        serialization_alias="receivedAt",
    )
    reason_code: str | None = Field(
        default=None,
        description="Machine-readable rejection reason code",
        validation_alias="reasonCode",
        serialization_alias="reasonCode",
    )
    reason_detail: str | None = Field(
        default=None,
        description="Human-readable rejection reason detail",
        validation_alias="reasonDetail",
        serialization_alias="reasonDetail",
    )

    @model_validator(mode="after")
    def _set_id_from_case(self) -> "VultronCaseLogEntry":
        """Compute ``id_`` from ``case_id`` and ``log_index``."""
        self.id_ = f"{self.case_id}/log/{self.log_index}"
        return self


#: Convenience type alias for optional references in use-case code.
VultronCaseLogEntryRef: TypeAlias = VultronCaseLogEntry | None

__all__ = ["VultronCaseLogEntry", "VultronCaseLogEntryRef"]
