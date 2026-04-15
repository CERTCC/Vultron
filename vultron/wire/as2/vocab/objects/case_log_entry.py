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
"""Wire-layer vocabulary class for :class:`CaseLogEntry`.

Defines :class:`CaseLogEntry`, the proper wire-layer representation of a
canonical case log entry used in ``Announce(CaseLogEntry)`` replication
activities.  This class inherits from
:class:`~vultron.wire.as2.vocab.objects.base.VultronObject` (an ``as_Base``
subclass) so that:

1. It auto-registers in the wire vocabulary as ``VOCABULARY["CaseLogEntry"]``
   via ``as_Base.__init_subclass__``, enabling correct DataLayer round-trips
   and vocabulary lookups in :func:`~vultron.wire.as2.rehydration.rehydrate`.
2. It satisfies the ``isinstance(obj, as_Object)`` check in
   :func:`~vultron.wire.as2.rehydration.rehydrate`.
3. :class:`~vultron.wire.as2.vocab.activities.sync.AnnounceLogEntryActivity`
   and :class:`~vultron.wire.as2.vocab.activities.sync.RejectLogEntryActivity`
   can use it as ``object_`` without type errors.

The canonical *domain* class is
:class:`~vultron.core.models.case_log_entry.VultronCaseLogEntry`.

The wire class deliberately omits the ``@model_validator`` that auto-computes
``id_`` from ``case_id``/``log_index``; activities received over the wire
always carry an explicit ``id``.

Spec: SYNC-01-002, SYNC-02-003, SYNC-02-004.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import Field

from vultron.core.models._helpers import _now_utc
from vultron.core.models.case_log import GENESIS_HASH
from vultron.core.models.case_log_entry import (  # noqa: F401
    VultronCaseLogEntry,
    VultronCaseLogEntryRef,
)
from vultron.wire.as2.vocab.objects.base import VultronObject


class CaseLogEntry(VultronObject):
    """Wire-layer representation of a canonical case log entry.

    All fields mirror
    :class:`~vultron.core.models.case_log_entry.VultronCaseLogEntry` but
    this class extends :class:`~vultron.wire.as2.vocab.objects.base.VultronObject`
    (an ``as_Base`` subclass) so it auto-registers in the wire vocabulary and
    satisfies the ``isinstance(obj, as_Object)`` check in rehydration.

    The ``id_`` is NOT auto-computed; it must be present in the incoming JSON
    (set by the sender's domain model).

    Spec: SYNC-01-002, SYNC-02-003, SYNC-02-004.
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
    term: Optional[int] = Field(
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
    reason_code: Optional[str] = Field(
        default=None,
        description="Machine-readable rejection reason code",
        validation_alias="reasonCode",
        serialization_alias="reasonCode",
    )
    reason_detail: Optional[str] = Field(
        default=None,
        description="Human-readable rejection reason detail",
        validation_alias="reasonDetail",
        serialization_alias="reasonDetail",
    )


__all__ = ["CaseLogEntry", "VultronCaseLogEntry", "VultronCaseLogEntryRef"]
