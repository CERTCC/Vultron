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
"""Persistable per-peer replication state for LedgerReconciliation/PeerLedgerSync.

Spec: SYNC-04-001, SYNC-04-002.
"""

from __future__ import annotations

import urllib.parse
from collections.abc import Mapping
from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import Field, model_validator

from vultron.core.models._helpers import now_utc
from vultron.core.models.base import NonEmptyString, with_record_id
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.retired_stored_fields import (
    RetiredFieldsRecord,
    RetiredStoredField,
)


class VultronReplicationState(RetiredFieldsRecord):
    """Tracks per-peer replication state for the CaseActor log fan-out.

    The ``id_`` is auto-computed as
    ``{case_id}/replication/{url_encoded_peer_id}`` so that the same
    peer always resolves to a stable key in the DataLayer.

    The join backfill keeps no state here: it commits with its ``Accept`` in
    one act (CLP-07-015), and whether an ``Accept`` is a duplicate is read
    from the participant record alone (CM-17-012).  The three
    ``join_backfill_*`` fields that once recorded it are retired (#5074), so a
    stored row that still carries one is refused.

    The ``last_reseed*`` fields record the CASE_MANAGER's last re-seed of
    the peer, which bounds the re-seed rate and tells a repeated divergence
    from a first one (SYNC-16-004, SYNC-16-008).

    Spec: SYNC-04-001, SYNC-04-002; the embargo pause is CM-10-005/006.
    """

    retired_stored_fields: ClassVar[Mapping[str, RetiredStoredField]] = {
        "join_backfill_target_index": RetiredStoredField(None, "#5074"),
        "join_backfill_last_sent_index": RetiredStoredField(None, "#5074"),
        "join_backfill_complete": RetiredStoredField(None, "#5074"),
    }

    type_: Literal["ReplicationState"] = Field(  # type: ignore[assignment]
        default="ReplicationState",
        validation_alias="type",
        serialization_alias="type",
    )
    case_id: NonEmptyString = Field(
        ..., description="URI of the parent VulnerabilityCase"
    )
    peer_id: NonEmptyString = Field(
        ..., description="Full URI of the participant actor"
    )
    last_acknowledged_hash: str = Field(
        default="",
        description=(
            "entry_hash of the last log entry acknowledged by this peer; "
            "empty string means no entries have been acknowledged yet "
            "(treat as genesis — replay from the beginning)"
        ),
        validation_alias="lastAcknowledgedHash",
        serialization_alias="lastAcknowledgedHash",
    )
    updated_at: datetime = Field(
        default_factory=now_utc,
        validation_alias="updatedAt",
        serialization_alias="updatedAt",
    )
    last_replayed_from_hash: str | None = Field(
        default=None,
        description=(
            "entry_hash the most recent Reject-triggered replay started from,"
            " used to suppress repeated full-ledger replays to a peer that has"
            " made no progress; None means no replay has run yet, and the"
            " empty string means the replay started from genesis"
            " (SYNC-15-003)"
        ),
        validation_alias="lastReplayedFromHash",
        serialization_alias="lastReplayedFromHash",
    )
    last_replayed_at: datetime | None = Field(
        default=None,
        description=(
            "When the most recent Reject-triggered replay was sent to this"
            " peer, used with last_replayed_from_hash to rate-limit replays to"
            " a peer that has made no progress; None means no replay has run"
            " yet (SYNC-15-003)"
        ),
        validation_alias="lastReplayedAt",
        serialization_alias="lastReplayedAt",
    )
    replays_at_position: int = Field(
        default=0,
        ge=0,
        description=(
            "How many consecutive non-empty replays have been sent to this"
            " peer from last_replayed_from_hash; each one doubles the cooldown"
            " before the next, and a replay from a different position resets"
            " it to 1. 0 means no replay has run yet (SYNC-15-003)"
        ),
        validation_alias="replaysAtPosition",
        serialization_alias="replaysAtPosition",
    )
    embargo_paused_from_index: int | None = Field(
        default=None,
        ge=0,
        description=(
            "log_index of the first canonical entry the embargo content gate"
            " withheld from this peer (CM-10-005); the backfill that admits"
            " the peer starts here (CM-10-006). None means the peer's stream"
            " is not paused"
        ),
        validation_alias="embargoPausedFromIndex",
        serialization_alias="embargoPausedFromIndex",
    )

    last_reseeded_at: datetime | None = Field(
        default=None,
        description=(
            "When the CASE_MANAGER last re-seeded this peer with"
            " Announce(VulnerabilityCase) in answer to its case-diverged"
            " fault; a fault inside the re-seed cooldown after it re-seeds"
            " nothing. None means the peer has never been re-seeded"
            " (SYNC-16-004)"
        ),
        validation_alias="lastReseededAt",
        serialization_alias="lastReseededAt",
    )
    last_reseed_position: LedgerPosition | None = Field(
        default=None,
        description=(
            "The ledger position the last re-seed's case copy named: a"
            " divergence fault for an entry at or before it, once the peer"
            " has acknowledged this position, means the CASE_MANAGER's case"
            " disagrees with its own ledger (SYNC-16-004, SYNC-16-008). None"
            " means the peer has never been re-seeded"
        ),
        validation_alias="lastReseedPosition",
        serialization_alias="lastReseedPosition",
    )

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``case_id`` and ``peer_id``."""
        if not isinstance(data, dict):
            return data
        case_id = data.get("case_id")
        peer_id = data.get("peer_id")
        if case_id is not None and peer_id is not None:
            slug = urllib.parse.quote(peer_id, safe="")
            data = with_record_id(data, f"{case_id}/replication/{slug}")
        return data
