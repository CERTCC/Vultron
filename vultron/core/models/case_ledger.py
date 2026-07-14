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

"""Append-only canonical case ledger for SYNC-1.

This module provides:

- :func:`compute_genesis_hash` — derive the per-case genesis hash from case
  identity metadata (CLP-08-001, CLP-08-002).
- :class:`HashChainLedgerRecord` — a single canonical ledger entry with
  hash-chain linkage and an optional embedded activity payload snapshot.
- :class:`CaseLedger` — an append-only, hash-chained ledger for a single case.

Per-peer replication state tracking is provided by
:class:`~vultron.core.models.replication_state.VultronReplicationState`
in ``vultron.core.models.replication_state``.

Design follows the single-writer CaseActor architecture described in
``notes/sync-ledger-replication.md`` and the requirements in
``specs/sync-ledger-replication.yaml`` (SYNC-01) and
``specs/case-ledger-processing.yaml`` (CLP-01 through CLP-08).

Hash chain:

- Each :class:`HashChainLedgerRecord` stores the SHA-256 hash of its own
  canonical content (``entry_hash``) and the hash of its immediate predecessor
  (``prev_log_hash``).
- The first entry uses the per-case genesis hash (see
  :func:`compute_genesis_hash`) as ``prev_log_hash`` (CLP-08-001,
  CLP-08-004).
- Canonical serialization uses deterministic JSON (``sort_keys=True``,
  compact separators, UTF-8) — compatible with RFC 8785 JCS and
  forward-compatible with a future Merkle Tree implementation.
- ``entry_hash`` is excluded from the content that is hashed (to avoid a
  self-referential dependency).

Append-only enforcement:

- :class:`CaseLedger` rejects any attempt to modify or remove existing
  entries.  New entries are appended via :meth:`CaseLedger.append`.

Per ``specs/sync-ledger-replication.yaml`` SYNC-01, SYNC-07,
``specs/case-ledger-processing.yaml`` CLP-02 through CLP-08, and
``notes/sync-ledger-replication.md``.
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from vultron.core.models._helpers import _now_utc

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-case genesis hash (CLP-08-001, CLP-08-002)
# ---------------------------------------------------------------------------


def compute_genesis_hash(
    case_id: str, created_at: datetime, case_actor_id: str
) -> str:
    """Return the per-case genesis hash for a case ledger.

    Derived as ``SHA-256(case_id + "|" + created_at.isoformat() + "|" +
    case_actor_id)``, where ``case_id`` is the canonical case URI,
    ``created_at`` is the case creation UTC timestamp, and
    ``case_actor_id`` is the canonical URI of the CaseActor.

    This anchors each case ledger to its origin identity and timestamp,
    replacing the former global zero-hash sentinel (CLP-08-001,
    CLP-08-002).

    Args:
        case_id: Canonical URI of the :class:`VulnerabilityCase`.
        created_at: TZ-aware UTC datetime at case creation.
        case_actor_id: Canonical URI of the CaseActor for this case.

    Returns:
        64-character lowercase hex SHA-256 digest string.

    Spec: CLP-08-001, CLP-08-002.
    """
    raw = f"{case_id}|{created_at.isoformat()}|{case_actor_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
# HashChainLedgerRecord
# ---------------------------------------------------------------------------


class HashChainLedgerRecord(BaseModel):
    """A single canonical case ledger entry.

    Each entry is created by the CaseActor's single authoritative write path
    and becomes immutable once appended to a :class:`CaseLedger`.

    Fields:
        case_id: URI of the :class:`VulnerabilityCase` this entry belongs to.
        log_index: Monotonically increasing integer scoped to ``case_id``.
            Assigned by :class:`CaseLedger.append`; MUST NOT be set by
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
            canonical content.  Per-case genesis hash (see
            :func:`compute_genesis_hash`) for the first entry in a case
            ledger.  Empty string when not yet known.
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
        description="Monotonically increasing index scoped to case_id; assigned by CaseLedger",
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
        default="",
        description="SHA-256 hex hash of immediate predecessor entry; per-case genesis hash for first",
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
    def _compute_entry_hash(self) -> "HashChainLedgerRecord":
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
# CaseLedger
# ---------------------------------------------------------------------------


class CaseLedger:
    """Append-only, hash-chained canonical case ledger.

    Maintains the full ordered list of :class:`HashChainLedgerRecord` objects
    for a single case. Enforces:

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

        from datetime import datetime, timezone
        case_id = "https://example.org/cases/abc123"
        case_actor_id = "https://example.org/actors/case-actor"
        created_at = datetime.now(timezone.utc)
        g_hash = compute_genesis_hash(case_id, created_at, case_actor_id)
        log = CaseLedger(case_id=case_id, genesis_hash=g_hash)
        entry = log.append(
            object_id="urn:uuid:report1",
            event_type="report_received",
            payload_snapshot={"id": "urn:uuid:report1"},
        )
        assert entry.log_index == 0
        assert entry.prev_log_hash == g_hash
        assert entry.verify_hash()

    Spec: SYNC-01-001, SYNC-01-002, SYNC-01-003, SYNC-07-001; CLP-04-001,
    CLP-04-003, CLP-08-002, CLP-08-004.
    """

    def __init__(self, case_id: str, genesis_hash: str) -> None:
        """Initialise an empty log for *case_id*.

        Args:
            case_id: URI of the :class:`VulnerabilityCase` this log tracks.
            genesis_hash: Per-case genesis hash computed via
                :func:`compute_genesis_hash`.  Used as ``prev_log_hash`` for
                the first entry and returned by :attr:`tail_hash` when the
                ledger is empty (CLP-08-004).
        """
        self._case_id = case_id
        self._genesis_hash = genesis_hash
        self._entries: list[HashChainLedgerRecord] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def case_id(self) -> str:
        """URI of the parent :class:`VulnerabilityCase`."""
        return self._case_id

    @property
    def entries(self) -> tuple[HashChainLedgerRecord, ...]:
        """All entries (recorded *and* rejected) as an immutable tuple."""
        return tuple(self._entries)

    @property
    def recorded_entries(self) -> tuple[HashChainLedgerRecord, ...]:
        """Projection of entries whose disposition is ``"recorded"``.

        Used for hash-chain computation and canonical state reconstruction.
        Per CLP-04-001, CLP-04-003.
        """
        return tuple(e for e in self._entries if e.disposition == "recorded")

    @property
    def tail_hash(self) -> str:
        """Hash of the last *recorded* entry, or the per-case genesis hash.

        This is the ``prev_log_hash`` that the next recorded entry MUST
        reference.  Rejected entries do not advance the tail (their hash is
        still chained, but only recorded entries participate in replication
        hash-chain computation per CLP-04-003).

        Returns:
            64-character lowercase hex SHA-256 string, or the per-case
            genesis hash (see :func:`compute_genesis_hash`) if no recorded
            entries exist (CLP-08-004).
        """
        recorded = self.recorded_entries
        return recorded[-1].entry_hash if recorded else self._genesis_hash

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
        payload_snapshot: dict[str, Any] = {},
        term: int | None = None,
        reason_code: str | None = None,
        reason_detail: str | None = None,
    ) -> HashChainLedgerRecord:
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
            The newly created and appended :class:`HashChainLedgerRecord`.

        Raises:
            ValueError: If *disposition* is ``"rejected"`` but *reason_code*
                is not provided.
        """
        if disposition == "rejected" and reason_code is None:
            raise ValueError(
                "reason_code is required for rejected HashChainLedgerRecord objects"
            )

        entry = HashChainLedgerRecord(
            case_id=self._case_id,
            log_index=self.next_index,
            disposition=disposition,
            term=term,
            object_id=object_id,
            event_type=event_type,
            payload_snapshot=payload_snapshot,
            prev_log_hash=self.tail_hash,
            reason_code=reason_code,
            reason_detail=reason_detail,
        )
        self._entries.append(entry)
        logger.info(
            "Committed ledger entry: case_id=%s event_type=%s log_index=%d disposition=%s",
            self._case_id,
            event_type,
            entry.log_index,
            disposition,
        )
        logger.debug(
            "Ledger entry detail: entry_hash=%.16s… payload_snapshot=%s",
            entry.entry_hash,
            payload_snapshot,
        )
        return entry

    def verify_chain(self) -> bool:
        """Return ``True`` if the full hash chain is internally consistent.

        Checks:

        1. Every entry's ``entry_hash`` matches its computed hash.
        2. Every entry's ``prev_log_hash`` equals the ``entry_hash`` of the
           previous *recorded* entry (or the per-case genesis hash for the
           first).
        3. Every entry's ``log_index`` equals its position in :attr:`entries`.

        Returns:
            ``True`` if the chain is intact; ``False`` on the first violation.
        """
        prev_recorded_hash = self._genesis_hash
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
