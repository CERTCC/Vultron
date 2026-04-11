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

"""Append-only canonical case event log for SYNC-1.

This module provides:

- :class:`CaseLogEntry` — a single canonical log entry with hash-chain
  linkage and an optional embedded activity payload snapshot.
- :class:`CaseEventLog` — an append-only, hash-chained log for a single case.
- :class:`ReplicationState` — per-peer last-acknowledged log hash for
  replication state tracking.

Design follows the single-writer CaseActor architecture described in
``notes/sync-log-replication.md`` and the requirements in
``specs/sync-log-replication.md`` (SYNC-01) and
``specs/case-log-processing.md`` (CLP-01 through CLP-05).

Hash chain:

- Each :class:`CaseLogEntry` stores the SHA-256 hash of its own canonical
  content (``entry_hash``) and the hash of its immediate predecessor
  (``prev_log_hash``).
- The first entry uses :data:`GENESIS_HASH` as ``prev_log_hash``.
- Canonical serialization uses deterministic JSON (``sort_keys=True``,
  compact separators, UTF-8) — compatible with RFC 8785 JCS and
  forward-compatible with a future Merkle Tree implementation.
- ``entry_hash`` is excluded from the content that is hashed (to avoid a
  self-referential dependency).

Append-only enforcement:

- :class:`CaseEventLog` rejects any attempt to modify or remove existing
  entries.  New entries are appended via :meth:`CaseEventLog.append`.

Per ``specs/sync-log-replication.md`` SYNC-01, SYNC-07, ``specs/case-log-processing.md``
CLP-02 through CLP-05, and ``notes/sync-log-replication.md``.
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from vultron.core.models._helpers import _now_utc

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Sentinel predecessor hash used for the first entry in a case log.
#: 64 hex-zero characters represent a SHA-256 zero-hash.
GENESIS_HASH: str = "0" * 64

# ---------------------------------------------------------------------------
# Disposition type
# ---------------------------------------------------------------------------

LogDisposition = Literal["recorded", "rejected"]


# ---------------------------------------------------------------------------
# Canonical serialization helpers
# ---------------------------------------------------------------------------


def _canonical_bytes(data: dict[str, Any]) -> bytes:
    """Return deterministic UTF-8 JSON bytes for *data*.

    Uses ``sort_keys=True`` and compact separators to produce a
    RFC 8785 JCS-compatible canonical form suitable for cryptographic hashing.
    ``datetime`` objects and other non-JSON-native types are coerced to
    strings via ``default=str``.

    Args:
        data: A dict whose values are JSON-serialisable.

    Returns:
        Compact UTF-8-encoded JSON bytes with sorted keys.
    """
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _sha256_hex(data: dict[str, Any]) -> str:
    """Return the lowercase hex SHA-256 digest of the canonical JSON of *data*.

    Args:
        data: A dict to canonicalise and hash.

    Returns:
        64-character lowercase hex SHA-256 digest string.
    """
    return hashlib.sha256(_canonical_bytes(data)).hexdigest()


# ---------------------------------------------------------------------------
# CaseLogEntry
# ---------------------------------------------------------------------------


class CaseLogEntry(BaseModel):
    """A single canonical case log entry.

    Each entry is created by the CaseActor's single authoritative write path
    and becomes immutable once appended to a :class:`CaseEventLog`.

    Fields:
        case_id: URI of the :class:`VulnerabilityCase` this entry belongs to.
        log_index: Monotonically increasing integer scoped to ``case_id``.
            Assigned by :class:`CaseEventLog.append`; MUST NOT be set by
            callers directly (CLP-02-006, SYNC-01-002).
        disposition: Outcome of CaseActor processing — ``"recorded"`` for
            accepted assertions; ``"rejected"`` for rejected ones.
        term: Raft cluster term at the time of append.  ``None`` (or ``0``)
            for single-node deployments (CLP-02-007).
        object_id: Full URI of the asserted activity or the primary object
            acted upon.
        event_type: Short machine-readable descriptor of the event kind
            (e.g. ``"embargo_accepted"``, ``"participant_joined"``).
        payload_snapshot: Normalized immutable snapshot of the asserted
            activity payload — sufficient for deterministic replay
            (CLP-02-003, SYNC-08-002).  Stored as a plain dict so that it
            survives DataLayer serialisation without wire-type coupling.
        prev_log_hash: SHA-256 hex hash of the immediate predecessor entry's
            canonical content.  :data:`GENESIS_HASH` for the first entry in
            a case log.
        entry_hash: SHA-256 hex hash of this entry's canonical content
            (excluding ``entry_hash`` itself).  Computed automatically by
            :meth:`model_validator` if not supplied.
        received_at: Server-generated TZ-aware UTC timestamp.
        reason_code: Machine-readable rejection reason code.  SHOULD be
            populated for ``"rejected"`` dispositions (CLP-02-005).
        reason_detail: Optional human-readable elaboration on the rejection
            reason.  MAY be populated for ``"rejected"`` dispositions.

    Spec: CLP-02-001 through CLP-02-007; SYNC-01-002, SYNC-01-003,
    SYNC-01-005, SYNC-07-001.
    """

    case_id: str = Field(
        ..., description="URI of the parent VulnerabilityCase"
    )
    log_index: int = Field(
        default=-1,
        description="Monotonically increasing index scoped to case_id; assigned by CaseEventLog",
        ge=-1,
    )
    disposition: LogDisposition = Field(
        default="recorded",
        description="Outcome: 'recorded' (accepted) or 'rejected'",
    )
    term: int | None = Field(
        default=None,
        description="Raft cluster term; None for single-node deployments",
    )
    object_id: str = Field(
        ..., description="Full URI of the asserted activity or primary object"
    )
    event_type: str = Field(
        ..., description="Short machine-readable event descriptor"
    )
    payload_snapshot: dict[str, Any] = Field(
        default_factory=dict,
        description="Normalized snapshot of the asserted activity payload for replay",
    )
    prev_log_hash: str = Field(
        default=GENESIS_HASH,
        description="SHA-256 hex hash of immediate predecessor entry; GENESIS_HASH for first",
    )
    entry_hash: str = Field(
        default="",
        description="SHA-256 hex hash of this entry's canonical content (auto-computed)",
    )
    received_at: datetime = Field(
        default_factory=_now_utc,
        description="Server-generated TZ-aware UTC timestamp at receipt",
    )
    reason_code: str | None = Field(
        default=None,
        description="Machine-readable rejection reason code (for rejected dispositions)",
    )
    reason_detail: str | None = Field(
        default=None,
        description="Human-readable rejection reason detail (for rejected dispositions)",
    )

    @model_validator(mode="after")
    def _compute_entry_hash(self) -> "CaseLogEntry":
        """Compute ``entry_hash`` from canonical content if not already set."""
        if not self.entry_hash:
            self.entry_hash = self._hash_content()
        return self

    def _hashable_dict(self) -> dict[str, Any]:
        """Return the canonical dict used for hash computation.

        Excludes ``entry_hash`` to avoid a self-referential dependency.
        All datetime values are serialised to ISO 8601 strings.
        """
        return {
            "case_id": self.case_id,
            "log_index": self.log_index,
            "disposition": self.disposition,
            "term": self.term,
            "object_id": self.object_id,
            "event_type": self.event_type,
            "payload_snapshot": self.payload_snapshot,
            "prev_log_hash": self.prev_log_hash,
            "received_at": self.received_at.isoformat(),
            "reason_code": self.reason_code,
            "reason_detail": self.reason_detail,
        }

    def _hash_content(self) -> str:
        """Compute and return the SHA-256 hex hash of this entry's content."""
        return _sha256_hex(self._hashable_dict())

    def verify_hash(self) -> bool:
        """Return ``True`` if ``entry_hash`` matches the computed hash.

        Can be used to detect tampering or serialisation corruption.
        """
        return self.entry_hash == self._hash_content()


# ---------------------------------------------------------------------------
# CaseEventLog
# ---------------------------------------------------------------------------


class CaseEventLog:
    """Append-only, hash-chained canonical case event log.

    Maintains the full ordered list of :class:`CaseLogEntry` objects for a
    single case.  Enforces:

    - **Append-only**: entries are immutable once added; no removal or
      replacement is permitted (SYNC-01-001).
    - **Hash-chain integrity**: each appended entry's ``prev_log_hash``
      references the ``entry_hash`` of the most recently appended entry
      (SYNC-01-003).
    - **Monotonically increasing** ``log_index`` values scoped to the case
      (SYNC-01-002).

    The log exposes two views:

    - :attr:`entries` — full audit log (both ``recorded`` and ``rejected``).
    - :attr:`recorded_entries` — filtered projection of ``recorded`` entries
      only, used for hash-chain computation and state reconstruction
      (CLP-04-001, CLP-04-003).

    Usage example::

        log = CaseEventLog(case_id="urn:uuid:abc123")
        entry = log.append(
            object_id="urn:uuid:report1",
            event_type="report_received",
            payload_snapshot={"id": "urn:uuid:report1"},
        )
        assert entry.log_index == 0
        assert entry.prev_log_hash == GENESIS_HASH
        assert entry.verify_hash()

    Spec: SYNC-01-001, SYNC-01-002, SYNC-01-003, SYNC-07-001; CLP-04-001,
    CLP-04-003.
    """

    def __init__(self, case_id: str) -> None:
        """Initialise an empty log for *case_id*.

        Args:
            case_id: URI of the :class:`VulnerabilityCase` this log tracks.
        """
        self._case_id = case_id
        self._entries: list[CaseLogEntry] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def case_id(self) -> str:
        """URI of the parent :class:`VulnerabilityCase`."""
        return self._case_id

    @property
    def entries(self) -> tuple[CaseLogEntry, ...]:
        """All entries (recorded *and* rejected) as an immutable tuple."""
        return tuple(self._entries)

    @property
    def recorded_entries(self) -> tuple[CaseLogEntry, ...]:
        """Projection of entries whose disposition is ``"recorded"``.

        Used for hash-chain computation and canonical state reconstruction.
        Per CLP-04-001, CLP-04-003.
        """
        return tuple(e for e in self._entries if e.disposition == "recorded")

    @property
    def tail_hash(self) -> str:
        """Hash of the last *recorded* entry, or :data:`GENESIS_HASH`.

        This is the ``prev_log_hash`` that the next recorded entry MUST
        reference.  Rejected entries do not advance the tail (their hash is
        still chained, but only recorded entries participate in replication
        hash-chain computation per CLP-04-003).

        Returns:
            64-character lowercase hex SHA-256 string, or
            :data:`GENESIS_HASH` if no recorded entries exist.
        """
        recorded = self.recorded_entries
        return recorded[-1].entry_hash if recorded else GENESIS_HASH

    @property
    def next_index(self) -> int:
        """Next ``log_index`` value that will be assigned on :meth:`append`.

        Returns:
            Integer equal to the current number of entries in the full log.
        """
        return len(self._entries)

    # ------------------------------------------------------------------
    # Append
    # ------------------------------------------------------------------

    def append(
        self,
        object_id: str,
        event_type: str,
        disposition: LogDisposition = "recorded",
        payload_snapshot: dict[str, Any] | None = None,
        term: int | None = None,
        reason_code: str | None = None,
        reason_detail: str | None = None,
    ) -> CaseLogEntry:
        """Append a new entry to the log and return it.

        Assigns ``log_index``, sets ``prev_log_hash`` from
        :attr:`tail_hash`, and computes ``entry_hash`` automatically.

        Args:
            object_id: Full URI of the asserted activity or primary object.
            event_type: Short machine-readable event kind descriptor.
            disposition: ``"recorded"`` (default) or ``"rejected"``.
            payload_snapshot: Normalised snapshot of the asserted activity
                payload for deterministic replay (CLP-02-003).
            term: Raft cluster term; ``None`` for single-node deployments.
            reason_code: Machine-readable rejection reason (for rejected).
            reason_detail: Human-readable rejection detail (for rejected).

        Returns:
            The newly created and appended :class:`CaseLogEntry`.

        Raises:
            ValueError: If *disposition* is ``"rejected"`` but *reason_code*
                is not provided.
        """
        if disposition == "rejected" and reason_code is None:
            raise ValueError(
                "reason_code is required for rejected CaseLogEntry objects"
            )

        entry = CaseLogEntry(
            case_id=self._case_id,
            log_index=self.next_index,
            disposition=disposition,
            term=term,
            object_id=object_id,
            event_type=event_type,
            payload_snapshot=payload_snapshot or {},
            prev_log_hash=self.tail_hash,
            reason_code=reason_code,
            reason_detail=reason_detail,
        )
        self._entries.append(entry)
        return entry

    def verify_chain(self) -> bool:
        """Return ``True`` if the full hash chain is internally consistent.

        Checks:

        1. Every entry's ``entry_hash`` matches its computed hash.
        2. Every entry's ``prev_log_hash`` equals the ``entry_hash`` of the
           previous *recorded* entry (or :data:`GENESIS_HASH` for the first).
        3. Every entry's ``log_index`` equals its position in :attr:`entries`.

        Returns:
            ``True`` if the chain is intact; ``False`` on the first violation.
        """
        prev_recorded_hash = GENESIS_HASH
        for pos, entry in enumerate(self._entries):
            if entry.log_index != pos:
                return False
            if not entry.verify_hash():
                return False
            if entry.disposition == "recorded":
                if entry.prev_log_hash != prev_recorded_hash:
                    return False
                prev_recorded_hash = entry.entry_hash
        return True


# ---------------------------------------------------------------------------
# ReplicationState
# ---------------------------------------------------------------------------


class ReplicationState(BaseModel):
    """Per-peer replication state tracked by the replication leader.

    Stores the last log entry hash acknowledged by a participant peer, so
    the leader can efficiently identify and replay missing entries on demand.

    Fields:
        peer_id: Full URI of the participant actor this state belongs to.
        last_acknowledged_hash: ``entry_hash`` of the last
            :class:`CaseLogEntry` the peer has confirmed receiving.
            Initialised to :data:`GENESIS_HASH` for new peers that have
            never received a replication message.
        updated_at: Server-generated TZ-aware UTC timestamp of the last
            acknowledgement.

    Spec: SYNC-04-001, SYNC-04-002.
    """

    peer_id: str = Field(..., description="Full URI of the participant actor")
    last_acknowledged_hash: str = Field(
        default=GENESIS_HASH,
        description=(
            "entry_hash of the last CaseLogEntry acknowledged by this peer; "
            "GENESIS_HASH for peers that have never received a replication message"
        ),
    )
    updated_at: datetime = Field(
        default_factory=_now_utc,
        description="Timestamp of the last acknowledgement from this peer",
    )
