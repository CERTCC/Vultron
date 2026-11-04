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


"""One hash-chained canonical case ledger entry (CLP-02, SYNC-01)."""

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from vultron.core.models._helpers import (
    format_timestamp,
    now_utc,
    timestamp_serializer,
)
from vultron.core.models.base import NonEmptyString, ValidatedAssignmentMixin
from vultron.core.models.case_ledger.hashing import _sha256_hex
from vultron.core.models.case_ledger_entry import CaseLedgerEntry

#: Reads a ``received_at`` the way the field does, so the hash input accepts
#: every spelling the stored field accepts.
_RECEIVED_AT: TypeAdapter[datetime] = TypeAdapter(datetime)


class HashChainLedgerRecord(ValidatedAssignmentMixin, BaseModel):
    """A single canonical case ledger entry.

    Each entry is created by the CaseActor's single authoritative write path
    and becomes immutable once appended to a :class:`CaseLedger`.

    Fields:
        case_id: URI of the :class:`VulnerabilityCase` this entry belongs to.
        log_index: Monotonically increasing integer scoped to ``case_id``.
            Assigned by :class:`CaseLedger.append`; MUST NOT be set by
            callers directly (CLP-02-006, SYNC-01-002).
        term: Raft cluster term at the time of append.  ``None`` (or ``0``)
            for single-node deployments (CLP-02-007).
        object_id: Full URI of the asserted activity or the primary object
            acted upon.
        semantic_type: The entry's semantic type, hashed under that key
            (e.g. ``"invite_actor_to_case"``; CLP-02-014).
        payload_snapshot: The asserted activity payload verbatim, the
            received body or the sealed blob sent — sufficient for
            deterministic replay (CLP-02-003, CLP-07-011, SYNC-08-002).
            Stored as a plain dict so that it survives DataLayer
            serialisation without wire-type coupling.
        prev_log_hash: SHA-256 hex hash of the immediate predecessor entry's
            canonical content.  Per-case genesis hash (see
            :func:`compute_genesis_hash`) for the first entry in a case
            ledger.  Empty string when not yet known.
        entry_hash: SHA-256 hex hash of this entry's canonical content
            (excluding ``entry_hash`` itself).  Computed automatically by
            :meth:`model_validator` if not supplied.
        received_at: Server-generated TZ-aware UTC timestamp.

    Spec: CLP-02-001 through CLP-02-007; SYNC-01-002, SYNC-01-003,
    SYNC-01-005, SYNC-07-001; CLP-04-007.
    """

    case_id: NonEmptyString = Field(
        ..., description="URI of the parent VulnerabilityCase"
    )
    log_index: int = Field(
        default=-1,
        description="Monotonically increasing index scoped to case_id; assigned by CaseLedger",
        ge=-1,
    )
    term: int | None = Field(
        default=None,
        description="Raft cluster term; None for single-node deployments",
    )
    object_id: NonEmptyString = Field(
        ..., description="Full URI of the asserted activity or primary object"
    )
    semantic_type: NonEmptyString = Field(
        ..., description="The entry's semantic type (CLP-02-014)"
    )
    payload_snapshot: dict[NonEmptyString, Any] = Field(
        default_factory=dict,
        description=(
            "The asserted activity payload verbatim, for replay (CLP-07-011)"
        ),
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
        default_factory=now_utc,
        description="Server-generated TZ-aware UTC timestamp at receipt",
    )
    _serialize_received_at = timestamp_serializer("received_at")

    @model_validator(mode="before")
    @classmethod
    def _compute_entry_hash(cls, data: Any) -> Any:
        """Compute ``entry_hash`` from canonical content if not already set."""
        if not isinstance(data, dict):
            return data
        if data.get("entry_hash"):
            return data
        data = dict(data)
        if "received_at" not in data:
            data["received_at"] = now_utc()
        received_val = data["received_at"]
        received_iso = format_timestamp(
            _RECEIVED_AT.validate_python(received_val)
        )
        hashable = {
            "case_id": data.get("case_id", ""),
            "log_index": data.get("log_index", -1),
            "term": data.get("term"),
            "object_id": data.get("object_id", ""),
            "semantic_type": data.get("semantic_type", ""),
            "payload_snapshot": data.get("payload_snapshot", {}),
            "prev_log_hash": data.get("prev_log_hash", ""),
            "received_at": received_iso,
        }
        data["entry_hash"] = _sha256_hex(hashable)
        return data

    def _hashable_dict(self) -> dict[str, Any]:
        """Return the canonical dict used for hash computation.

        Excludes ``entry_hash`` to avoid a self-referential dependency.
        All datetime values are serialised in the fixed form of
        :func:`format_timestamp` (CS-13-007), so one instant hashes the same
        whether or not its microseconds are zero.

        ``received_at`` is the CaseActor's server-generated UTC timestamp,
        set once at append time and never modified.  Replicas receive this
        entry via ``Announce(CaseLedgerEntry)`` with ``received_at`` already
        embedded; they MUST preserve its value rather than regenerating it,
        otherwise ``verify_hash()`` will return ``False`` on any replica that
        re-computes the hash (CLP-02-008, SYNC-01-003).

        ``payload_snapshot`` is the activity as captured by the CaseActor at
        commit time.  Replicas receive and store it verbatim; they MUST NOT
        reconstruct it locally, as local actor state (e.g. inbox item counts,
        timestamps) may differ from the CaseActor's snapshot (SYNC-01-003).
        """
        return {
            "case_id": self.case_id,
            "log_index": self.log_index,
            "term": self.term,
            "object_id": self.object_id,
            "semantic_type": self.semantic_type,
            "payload_snapshot": self.payload_snapshot,
            "prev_log_hash": self.prev_log_hash,
            "received_at": format_timestamp(self.received_at),
        }

    def _hash_content(self) -> str:
        """Compute and return the SHA-256 hex hash of this entry's content."""
        return _sha256_hex(self._hashable_dict())

    def verify_hash(self) -> bool:
        """Return ``True`` if ``entry_hash`` matches the computed hash.

        Can be used to detect tampering or serialisation corruption.
        """
        return self.entry_hash == self._hash_content()

    def to_ledger_entry(self) -> CaseLedgerEntry:
        """Return the stored and replicated form of this record.

        ``received_at`` is copied, never re-stamped, because it is hashed
        content: an entry carrying a later time than the one ``entry_hash``
        was computed over no longer reproduces its own hash (SYNC-01-003).
        ``published`` is the CASE_MANAGER's commit stamp (CLP-14-002); the
        record is committed at the instant it is stamped, so it takes the
        same value.
        """
        return CaseLedgerEntry(
            case_id=self.case_id,
            log_index=self.log_index,
            term=self.term,
            log_object_id=self.object_id,
            semantic_type=self.semantic_type,
            payload_snapshot=dict(self.payload_snapshot),
            prev_log_hash=self.prev_log_hash,
            entry_hash=self.entry_hash,
            received_at=self.received_at,
            published=self.received_at,
        )

    @classmethod
    def from_ledger_entry(cls, entry: CaseLedgerEntry) -> Self:
        """Rebuild the hashed record from a stored or received entry.

        The entry's ``entry_hash`` is carried as stated, not recomputed, so
        :meth:`verify_hash` on the result tells whether the entry's content
        reproduces the hash it claims.  An entry with no ``entry_hash`` gets
        one computed here, so use :func:`ledger_entry_hash_intact` to check a
        received entry.
        """
        return cls(
            case_id=entry.case_id,
            log_index=entry.log_index,
            term=entry.term,
            object_id=entry.log_object_id,
            semantic_type=entry.semantic_type,
            payload_snapshot=dict(entry.payload_snapshot),
            prev_log_hash=entry.prev_log_hash,
            entry_hash=entry.entry_hash,
            received_at=entry.received_at,
        )


def ledger_entry_hash_intact(entry: CaseLedgerEntry) -> bool:
    """Return ``True`` if *entry* states a hash its content reproduces.

    An entry that states no hash is not intact: it carries nothing to check
    (SYNC-03-006).
    """
    return bool(entry.entry_hash) and (
        HashChainLedgerRecord.from_ledger_entry(entry).verify_hash()
    )
