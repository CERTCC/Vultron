# Sync Log Replication — Design Notes

**Relates to**: `specs/sync-log-replication.md`, `plan/IMPLEMENTATION_PLAN.md`
PRIORITY-400 (SYNC-1 through SYNC-4)

---

## Architecture Overview

Vultron is a **log-centric architecture** in which the CaseActor is the
authoritative single writer of an append-only, hash-chained log, and all
externally visible system state is a deterministic projection of that log.

Key properties:

- **Single-writer regime**: The CaseActor (acting as de facto replication
  leader) is the only node that appends to the authoritative log. This
  simplifies consistency guarantees and avoids concurrent-write conflicts.
- **Eventual consistency**: Participants synchronize by receiving replicated
  log entries; their local state converges to the CaseActor's state as
  entries are delivered.
- **Forward compatibility**: The single-writer design deliberately preserves
  forward compatibility with a Raft-like consensus model for leader election
  and failover; however, failover semantics are out of scope for the current
  phase and MUST NOT be implicitly assumed.

---

## Hash-Chain Design

Each log entry carries a cryptographic hash of its own content and
references the hash of the immediate predecessor, forming a
**forward-linked Merkle chain**.

- Synchronization state is communicated via hashes rather than indices.
  Both sides have access to the same hashes, so the CaseActor can replay
  all entries following the last hash a participant reports having received,
  without needing to track numeric indices.
- The first entry uses a well-known sentinel predecessor hash (e.g.,
  all-zeros).

Design Decision: Hashes are preferred over sequence indices for
synchronization state reporting because:

1. They are self-verifying — a receiver can check that a received entry
   matches its stated hash before accepting it.
2. They decouple synchronization position from any particular numbering
   scheme, which simplifies replay after log compaction or migration.

---

## Log Position in Activity Context

When a Participant Actor sends **any** message to the CaseActor, it
SHOULD include the hash of its last accepted log entry as a parameter
in the activity's `context` field. This allows the CaseActor to
proactively detect that a participant is behind and immediately replay
missing entries without waiting for an explicit sync request.

This is an optimization that reduces round trips for the common case of
a slightly-behind participant.

---

## Implementation Phases

| Phase  | Description                                               |
|--------|-----------------------------------------------------------|
| SYNC-1 | Local append-only log with hash-chain indexing            |
| SYNC-2 | One-way replication from CaseActor to Participant Actors  |
| SYNC-3 | Full sync loop with retry/backoff                         |
| SYNC-4 | Multi-peer synchronization (enables future Raft consensus) |

### SYNC-1 Scope

The `CaseEvent` model (`vultron/wire/as2/vocab/objects/case_event.py`)
provides the foundation. SYNC-1 extends it to a true append-only log
with hash-chain indexing.

Core domain classes (transport-agnostic):

- `CaseEventLog` — append-only log; enforces immutability and hash-chain
- `ReplicationState` — per-peer last-acknowledged hash

Adapter responsibilities:

- AS2 `Announce` activity mapping (outbound replication message)
- Inbound handler for `Announce` (participant receiving a log entry)
- File/database log storage

### SYNC-2 Scope

One-way replication from CaseActor to each Participant Actor:

- Strict conflict handling: reject mismatched `prev_log_hash`, respond
  with last-accepted hash
- Sender retries from the entry following the reported last-accepted hash

Design Decision (blocks SYNC-2): Reconcile "replication leadership" with
"Case Ownership". Case Ownership governs who controls the case lifecycle
(e.g., closing the case, transferring ownership). Replication leadership
governs which node currently accepts writes to the log. These are distinct:

- A case ownership transfer implies a replication leadership change.
- A replication leadership change alone does NOT imply an ownership transfer.

---

## System Invariants

All components interacting with state, messaging, or storage MUST treat
the log as the sole source of truth and MUST preserve the following
invariants under normal operation and partial failure:

1. **Append-only integrity**: Log entries are immutable once committed and
   are uniquely identified by their content hash.
2. **Deterministic projection**: Given an identical log prefix, all
   compliant implementations MUST derive identical state.
3. **Idempotent replay**: Reprocessing any log prefix (including duplicates)
   MUST NOT change the resulting state.
4. **Monotonic visibility**: Participants MUST NOT regress their acknowledged
   log position.
5. **Reject-on-divergence**: Entries that do not extend the current hash
   chain MUST be rejected and MUST trigger resynchronization.

---

## Open Questions

- **Commit/ack semantics**: When is an entry considered "accepted" vs.
  "durable"? What does durability mean in a single-writer regime before
  SYNC-4 introduces quorum?
- **Log compaction**: Will the log grow without bound? Is there a policy
  for archiving old entries while preserving the hash-chain anchor?
- **Trust model / key management**: Each CaseActor and participating node
  MUST eventually possess a cryptographic identity. The specification must
  define how keys are generated, distributed, rotated, and revoked, and
  how trust anchors are established (e.g., pinned keys vs. PKI). This is
  `PROD_ONLY` scope but SHOULD be designed before SYNC-3 to avoid
  retrofitting later.

---

## Related

- `specs/sync-log-replication.md` — normative requirements
- `plan/IMPLEMENTATION_PLAN.md` — SYNC-1 through SYNC-4 tasks
- `docs/adr/` — architectural decisions for CaseActor, per-actor DataLayer
- `notes/case-state-model.md` — CaseEvent model and trusted timestamps
