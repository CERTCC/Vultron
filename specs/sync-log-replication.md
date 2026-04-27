# Case Event Log Synchronization Specification

## Overview

Requirements for the append-only canonical recorded case log, replication
transport, conflict handling, per-peer state tracking, and retry semantics
for distributed case state synchronization across Participant Actors.

**Source**: `plan/IMPLEMENTATION_PLAN.md` PRIORITY-400 (SYNC-1 through
SYNC-4), `plan/IMPLEMENTATION_NOTES.md` (2026-03-26 SYNC design notes)
**Cross-references**: `specs/case-management.yaml`,
`specs/case-log-processing.yaml`, `specs/outbox.yaml`,
`specs/idempotency.yaml`
**Note**: Before implementing SYNC-1, create
`notes/sync-log-replication.md` capturing the RAFT-inspired design notes.
A `notes/` file is the appropriate place for design approach details; this
spec captures the normative requirements.

---

## Append-Only Log

- `SYNC-01-001` The canonical recorded case log MUST be append-only; log
  entries MUST be immutable once appended
  - Broader local case audit history MAY exist outside the replicated chain;
    see `specs/case-log-processing.yaml`
- `SYNC-01-002` Each log entry MUST carry a monotonically increasing index
  scoped to its case
  - `CaseLogEntry` MUST include `log_index` as a named field so that all
    downstream components and wire representations are index-aware from
    SYNC-1 onwards
- `SYNC-01-003` Each log entry MUST include a cryptographic hash of its own
  content and MUST reference the hash of its immediate predecessor, forming
  a forward-linked hash chain (Merkle chain style)
  - The first entry in a case log MUST use a sentinel predecessor hash (e.g.,
    a zero-hash or well-known constant)
  - `PROD_ONLY` The CaseActor MUST cryptographically sign each log entry,
    incorporating the previous entry's hash to create a verifiable chain
    of custody
- `SYNC-01-004` Canonical recorded log entries MUST be written through the
  CaseActor's single authoritative write path
  - `SYNC-01-004` depends-on `CLP-02-001`
  - `SYNC-01-004` implements `CM-02-009`
- `SYNC-01-005` The hash-chain log entry format MUST be designed to be
  forward-compatible with a future Merkle Tree implementation
  - Log entries MUST be structured so they can serve as leaf nodes in a Merkle
    Tree without requiring structural changes to the entry format itself
  - Entry content committed to the hash computation MUST be stable and
    canonical; introducing optional or variable fields after entries have been
    signed will invalidate existing hash chains
  - See `notes/sync-log-replication.md` "Canonical Serialization" for the
    required serialization constraints

## Replication Transport

- `SYNC-02-001` Log replication between CaseActor and Participant Actors MUST
  use ActivityStreams `Announce` activities as the transport envelope for
  canonical recorded log content
  - `SYNC-02-001` is-refined-by `CLP-04-004`
- `SYNC-02-002` Each replication message MUST identify the sender, target
  recipient, the log entry hash, and the predecessor hash
- `SYNC-02-003` Replication MUST originate from the replication leader
  (initially the CaseActor) and be sent to each Participant Actor
  individually
- `SYNC-02-004` Each `Announce(CaseLogEntry)` activity MUST embed the full
  inline `CaseLogEntry` object in its `object` field; a URI-only reference
  MUST NOT be used, because the recipient needs all entry fields (including
  `prev_log_hash` and `entry_hash`) to validate the hash chain without an
  additional round-trip to the sender's DataLayer

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

- `SYNC-03-004` When a Participant Actor sends any message to the CaseActor,
  it SHOULD include the hash of its last accepted canonical recorded log entry
  as a parameter in the activity's context field
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
- `SYNC-06-003` The SYNC-1 through SYNC-4 phases implement a **single-node
  CaseActor configuration** — a degenerate Raft cluster of one. A single-node
  CaseActor is always the leader and always has write authority; no election
  is needed.
  - A single-node configuration MUST always be a supported deployment option,
    even when multi-node CaseActor cluster support is available.
- `SYNC-06-004` A future multi-node CaseActor cluster (Phase 3) provides
  high-availability write authority via Raft consensus. This is a distinct
  replication tier from participant replication:
  - *CaseActor cluster replication*: N CaseActor instances synchronize among
    themselves using Raft to elect a leader and replicate the log.
  - *Participant replication*: The cluster leader fans out
    `Announce(CaseLogEntry)` entries to Participant Actors for state
    convergence.
  - Both tiers share the same `Announce(CaseLogEntry)` wire envelope.

## Commit Discipline

- `SYNC-09-001` A log entry is **committed** when it has been durably
  appended to the authoritative log and is safe to apply to the case state
  machine
  - In a single-node CaseActor: every append is an immediate commit
  - In a multi-node CaseActor cluster (Phase 3): an entry is committed when
    the leader has received acknowledgement from a majority of cluster peers
- `SYNC-09-002` External Vultron messages (activities sent to Participant
  Actors or other protocol participants) MUST only be emitted after the
  associated `CaseLogEntry` is committed
  - Participant replication fan-out (`Announce(CaseLogEntry)`) is therefore
    always downstream of the commit index
- `SYNC-09-003` The CaseActor's behavior tree execution MUST be gated on
  holding leadership role; in single-node this is always satisfied; in
  multi-node this MUST be checked against the Raft leader state
  - See `notes/sync-log-replication.md` "Behavior Tree Leadership Guard" for
    the design approach

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
- `SYNC-08-002` Deterministic projection: given an identical canonical
  recorded log prefix, all compliant implementations MUST derive identical
  state
- `SYNC-08-003` Idempotent replay: reprocessing any canonical recorded log
  prefix (including duplicates) MUST NOT change the resulting state
- `SYNC-08-004` Monotonic visibility: participants MUST NOT regress their
  acknowledged log position
- `SYNC-08-005` (MUST) Reject-on-divergence: entries that do not extend the current
  hash chain MUST be rejected and MUST trigger resynchronization

**Note**: All specs interacting with state, messaging, or storage MUST treat
the canonical recorded log as the sole source of truth for replica state and
MUST NOT introduce alternative state authorities or side-channel
synchronization mechanisms. SYNC-1 through SYNC-4 implement a single-node
CaseActor configuration (permanent leader, immediate commit, no election).
Multi-node CaseActor cluster semantics (Raft leader election, majority-quorum
commit) are deferred to a future phase and MUST NOT be implicitly assumed by
implementations in the current scope. See `notes/sync-log-replication.md`
and `specs/case-log-processing.yaml` for the full architectural rationale.
