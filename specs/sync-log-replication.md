# Case Event Log Synchronization Specification

## Overview

Requirements for the append-only case event log, replication transport,
conflict handling, per-peer state tracking, and retry semantics for
distributed case state synchronization across Participant Actors.

**Source**: `plan/IMPLEMENTATION_PLAN.md` PRIORITY-400 (SYNC-1 through
SYNC-4), `plan/IMPLEMENTATION_NOTES.md` (2026-03-26 SYNC design notes)
**Cross-references**: `specs/case-management.md`, `specs/outbox.md`,
`specs/idempotency.md`
**Note**: Before implementing SYNC-1, create
`notes/sync-log-replication.md` capturing the RAFT-inspired design notes.
A `notes/` file is the appropriate place for design approach details; this
spec captures the normative requirements.

---

## Append-Only Log

- `SYNC-01-001` The local case event log MUST be append-only; log entries
  MUST be immutable once appended
- `SYNC-01-002` Each log entry MUST carry a monotonically increasing index
  scoped to its case
- `SYNC-01-003` Each log entry MUST include a cryptographic hash of its own
  content and MUST reference the hash of its immediate predecessor, forming
  a forward-linked hash chain (Merkle chain style)
  - The first entry in a case log MUST use a sentinel predecessor hash (e.g.,
    a zero-hash or well-known constant)
  - `PROD_ONLY` The CaseActor MUST cryptographically sign each log entry,
    incorporating the previous entry's hash to create a verifiable chain
    of custody
- `SYNC-01-004` Log entries MUST be written via `VulnerabilityCase.record_event()`
  as the single authoritative write path
  - SYNC-01-004 implements CM-02-009 (case-management.md)

## Replication Transport

- `SYNC-02-001` (MUST) Log replication between CaseActor and Participant Actors
  MUST use ActivityStreams `Announce` activities as the transport envelope
- `SYNC-02-002` Each replication message MUST identify the sender, target
  recipient, the log entry hash, and the predecessor hash
- `SYNC-02-003` Replication MUST originate from the replication leader
  (initially the CaseActor) and be sent to each Participant Actor
  individually

## Conflict Handling

- `SYNC-03-001` A receiver MUST reject a replication message whose
  predecessor hash does not match the receiver's current log tail hash
  - On rejection, the receiver MUST respond with the hash of the last
    accepted entry so the sender can identify and replay missing entries
- `SYNC-03-002` On receiving a rejection, the sender MUST retry replication
  starting from the entry following the last accepted hash reported by
  the receiver
- `SYNC-03-003` Replication MUST be idempotent: repeated delivery of the
  same log entry MUST NOT produce duplicate entries in the receiver's log
  - SYNC-03-003 implements IDEM-01-001 (idempotency.md)

## Log State in Context

- `SYNC-03-004` (SHOULD) When a Participant Actor sends any message to the CaseActor,
  it SHOULD include the hash of its last accepted log entry as a parameter
  in the activity's context field
  - This allows the CaseActor to proactively detect that a participant is
    behind and immediately replay missing entries without waiting for an
    explicit sync request

## Per-Peer Replication State

- `SYNC-04-001` The replication leader MUST track per-peer state including
  at minimum the last acknowledged log entry hash for each peer
- `SYNC-04-002` Per-peer replication state MUST be persisted via the
  DataLayer so that it survives a leader restart

## Retry and Backoff

- `SYNC-05-001` The replication sender SHOULD implement retry with
  exponential backoff on delivery failure
- `SYNC-05-002` Retry and backoff parameters SHOULD be configurable;
  default values MUST be documented

## Leadership and Ownership

- `SYNC-06-001` Replication leadership SHOULD be treated as distinct from
  case ownership
  - A case ownership transfer implies a replication leadership change; a
    leadership change alone does not imply an ownership transfer
- `SYNC-06-002` (SHOULD) The conditions under which replication leadership changes
  SHOULD be documented in `notes/sync-log-replication.md`

## Testing

- `SYNC-07-001` Unit tests MUST cover append-only semantics: entries are
  immutable, hashes are unique, and predecessor hash references are set correctly
- `SYNC-07-002` Integration tests MUST cover the full single-peer
  replication cycle: leader appends an entry, sends an `Announce` activity,
  and the receiver validates the predecessor hash and appends the entry
- `SYNC-07-003` Tests MUST cover conflict and idempotency scenarios:
  mismatched predecessor hash, duplicate delivery, and leader retry after
  rejection

## System Invariants

The log-centric architecture requires the following invariants to be
preserved under normal operation and partial failure:

- `SYNC-08-001` Append-only integrity: log entries MUST be immutable once
  committed and MUST be uniquely identified by their content hash
- `SYNC-08-002` (MUST) Deterministic projection: given an identical log prefix,
  all compliant implementations MUST derive identical state
- `SYNC-08-003` (MUST NOT) Idempotent replay: reprocessing any log prefix (including
  duplicates) MUST NOT change the resulting state
- `SYNC-08-004` Monotonic visibility: participants MUST NOT regress their
  acknowledged log position
- `SYNC-08-005` (MUST) Reject-on-divergence: entries that do not extend the current
  hash chain MUST be rejected and MUST trigger resynchronization

**Note**: All specs interacting with state, messaging, or storage MUST treat
the log as the sole source of truth and MUST NOT introduce alternative state
authorities or side-channel synchronization mechanisms. Failover and
consensus semantics (e.g., Raft leader election) are out of scope for the
current phase and MUST NOT be implicitly assumed by other specifications.
See `notes/sync-log-replication.md` for the full architectural rationale.
