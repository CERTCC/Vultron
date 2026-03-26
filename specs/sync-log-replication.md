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

## Append-Only Log (MUST)

- `SYNC-01-001` The local case event log MUST be append-only; log entries
  MUST be immutable once appended
- `SYNC-01-002` Each log entry MUST carry a monotonically increasing index
  scoped to its case
- `SYNC-01-003` Each log entry MUST reference the index of its immediate
  predecessor to support sequence verification
  - The first entry in a case log MUST use a sentinel predecessor value
    (e.g., `prev_log_index: 0`)
- `SYNC-01-004` Log entries MUST be written via `VulnerabilityCase.record_event()`
  as the single authoritative write path
  - SYNC-01-004 implements CM-02-009 (case-management.md)

## Replication Transport (MUST)

- `SYNC-02-001` Log replication between CaseActor and Participant Actors
  MUST use ActivityStreams `Announce` activities as the transport envelope
- `SYNC-02-002` Each replication message MUST identify the sender, target
  recipient, the log entry index, and the predecessor index
- `SYNC-02-003` Replication MUST originate from the replication leader
  (initially the CaseActor) and be sent to each Participant Actor
  individually

## Conflict Handling (MUST)

- `SYNC-03-001` A receiver MUST reject a replication message whose
  predecessor index does not match the receiver's current log tail
  - On rejection, the receiver MUST respond with the highest accepted log
    index
- `SYNC-03-002` On receiving a rejection, the sender MUST retry replication
  starting from the index indicated by the receiver
- `SYNC-03-003` Replication MUST be idempotent: repeated delivery of the
  same log entry MUST NOT produce duplicate entries in the receiver's log
  - SYNC-03-003 implements IDEM-01-001 (idempotency.md)

## Per-Peer Replication State (MUST)

- `SYNC-04-001` The replication leader MUST track per-peer state including
  at minimum the last acknowledged log index for each peer
- `SYNC-04-002` Per-peer replication state MUST be persisted via the
  DataLayer so that it survives a leader restart

## Retry and Backoff (SHOULD)

- `SYNC-05-001` The replication sender SHOULD implement retry with
  exponential backoff on delivery failure
- `SYNC-05-002` Retry and backoff parameters SHOULD be configurable;
  default values MUST be documented

## Leadership and Ownership (SHOULD)

- `SYNC-06-001` Replication leadership SHOULD be treated as distinct from
  case ownership
  - A case ownership transfer implies a replication leadership change; a
    leadership change alone does not imply an ownership transfer
- `SYNC-06-002` The conditions under which replication leadership changes
  SHOULD be documented in `notes/sync-log-replication.md`

## Testing (MUST)

- `SYNC-07-001` Unit tests MUST cover append-only semantics: entries are
  immutable, indices are monotonically increasing, and predecessor
  references are set correctly
- `SYNC-07-002` Integration tests MUST cover the full single-peer
  replication cycle: leader appends an entry, sends an `Announce` activity,
  and the receiver validates and appends the entry
- `SYNC-07-003` Tests MUST cover conflict and idempotency scenarios:
  mismatched predecessor index, duplicate delivery, and leader retry after
  rejection
