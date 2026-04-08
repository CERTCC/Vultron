# Sync Log Replication — Design Notes

**Relates to**: `specs/sync-log-replication.md`, `plan/IMPLEMENTATION_PLAN.md`
PRIORITY-400 (SYNC-1 through SYNC-4)

---

## Architecture Overview

Vultron is a **log-centric architecture** in which the CaseActor is the
authoritative single writer of an append-only, hash-chained **canonical
recorded log**, and all externally visible replicated state is a deterministic
projection of that recorded log.

Key properties:

- **Single-writer regime**: The CaseActor (acting as de facto replication
  leader) is the only node that appends to the authoritative log. This
  simplifies consistency guarantees and avoids concurrent-write conflicts.
- **Eventual consistency**: Participants synchronize by receiving replicated
  log entries; their local state converges to the CaseActor's state as
  entries are delivered.
- **Audit vs replication split**: The CaseActor MAY keep a broader local case
  audit trail including rejected assertion outcomes, but only the recorded
  canonical projection participates in replication and hash chaining.
- **Single-node Raft framing**: The SYNC-1 through SYNC-4 phases effectively
  implement a single-node Raft cluster. The CaseActor is permanently the
  leader (no election needed), and every append is an immediate commit. A
  single-node configuration MUST always be supported as the degenerate case
  of the general distributed model.
- **Two-tier replication**: Vultron has two distinct replication tiers that
  MUST NOT be conflated. (1) *CaseActor cluster replication* synchronizes
  multiple CaseActor instances for high-availability write authority — this
  is the scope of the Raft consensus protocol. (2) *Participant replication*
  delivers the canonical recorded log from the CaseActor cluster leader to
  Participant Actors for state convergence — this is the scope of SYNC-1–4.
  Both tiers share the same `Announce(CaseLogEntry)` wire format, but serve
  different purposes.
- **Forward compatibility**: The single-writer, single-node design explicitly
  preserves forward compatibility with a multi-node Raft cluster for
  high-availability failover. A future Phase 3 adds N-node CaseActor cluster
  support using standard Raft (static membership, log-completeness election,
  no priority tiebreaker). Failover semantics are out of scope for SYNC-1–4
  and MUST NOT be implicitly assumed by implementations in those phases.

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
| SYNC-4 | Multi-peer synchronization (completes single-node CaseActor participant replication) |

### SYNC-1 Scope

The current `CaseEvent` model (`vultron/wire/as2/vocab/objects/case_event.py`)
provides the foundation. SYNC-1 extends it toward a true canonical recorded
log with hash-chain indexing; the richer long-term content model is described
in `notes/case-log-authority.md`.

Core domain classes (transport-agnostic):

- `CaseEventLog` — append-only log; enforces immutability and hash-chain
- `ReplicationState` — per-peer last-acknowledged hash

`CaseLogEntry` fields for SYNC-1:

- `log_index` — monotonically increasing integer scoped to the case (MUST;
  see SYNC-01-002). Added in SYNC-1 so downstream code and wire format are
  index-aware from the start.
- `term` — Raft term number (OPTIONAL in SYNC-1; defaults to `null` or `0`
  in single-node deployments; becomes required when multi-node CaseActor
  cluster is introduced in Phase 3).

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

## Commit Discipline

A log entry is **committed** when it has been durably appended to the
authoritative log and is safe to apply to the case state machine and emit
externally.

- In a **single-node** CaseActor (SYNC-1–4): every append is an immediate
  commit. There is no replication quorum to wait for.
- In a **multi-node CaseActor cluster** (Phase 3 Raft): an entry is committed
  once the leader has received acknowledgement from a majority of cluster
  peers. The leader only advances the commit index after majority ack.

**Emit-after-commit invariant**: External Vultron messages (activities sent
to Participant Actors or other protocol peers) MUST only be emitted after the
associated `CaseLogEntry` is committed. Participant replication fan-out
(`Announce(CaseLogEntry)`) is therefore always downstream of the commit index
in both single-node and multi-node configurations.

This discipline ensures that activities a node claims to have taken are
durably recorded and cannot be rolled back by a leadership change.

---

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

## CaseActor Cluster (Phase 3)

A future Phase 3 adds multi-node CaseActor cluster support for
**high-availability write authority**. Key design decisions settled during
planning:

- **Architecture**: N CaseActor instances form a Raft cluster. The leader
  holds exclusive write authority. Follower instances replicate the log but
  do not emit case protocol actions.
- **Single-node is a first-class case**: A single CaseActor instance is a
  degenerate cluster of 1 and MUST always be a supported configuration. Phase
  3 is a generalization, not a replacement.
- **Standard Raft election**: Leader election uses log completeness only
  (highest `(term, log_index)` wins). No priority tiebreaker. Pre-vote is
  deferred as a future optimization.
- **Static membership**: Cluster size is a deployment configuration parameter.
  Dynamic membership changes are out of scope.
- **Wire format**: Raft cluster messages (AppendEntries, heartbeat, vote
  request/response) use the same ActivityPub inbox as CVD protocol messages,
  mapped to distinct `MessageSemantics` values. `Announce(CaseLogEntry)` is
  the unified replication envelope for both CaseActor cluster AppendEntries
  and Participant Actor replication.
- **AS2 activity mapping**:

  | Raft function      | AS2 activity type                        |
  |--------------------|------------------------------------------|
  | AppendEntries      | `Announce(CaseLogEntry)`                 |
  | Heartbeat          | `Announce(CaseActorHeartbeat)` (new obj) |
  | Vote request       | `Question(OneOf)`                        |
  | Vote granted       | `Accept(Question)`                       |
  | Vote denied        | `Reject(Question)`                       |
  | Leader declaration | `Announce(CaseActorLeadership)` (new obj)|

  New Vultron-namespace objects (`CaseActorHeartbeat`,
  `CaseActorLeadership`) use existing AS2 activity verbs; they do not
  require new AS2 activity types.

- **Leadership and Case Ownership**: Raft leadership is strictly a cluster
  availability mechanism. It MUST NOT be confused with Case Ownership (which
  governs protocol lifecycle permissions). A case ownership transfer implies
  a leadership handover; a leadership failover does not imply an ownership
  transfer.

---

## Behavior Tree Leadership Guard

The case behavior tree (BT) MUST only execute on the current Raft cluster
leader. This ensures that only the leader generates `CaseLogEntry` objects
and emits external Vultron activities.

Design approach:

- Add a **leadership role-check port** to the BT bridge
  (`vultron/core/behaviors/bridge.py`). The port is a simple callable or
  Protocol that returns `True` if the calling node is the current leader.
- In SYNC-1–4 (single-node): the port implementation always returns `True`.
- In Phase 3 (multi-node): the port queries the Raft state machine.

This port SHOULD be added during SYNC-1 so that the seam already exists in
the BT bridge and Phase 3 only needs to provide a real implementation. The
port being permanently `True` in single-node imposes zero runtime cost.

---

## Open Questions

- **Commit/ack semantics**: *Resolved* — see "Commit Discipline" above.
  In single-node, an entry is committed on append. In multi-node (Phase 3),
  an entry is committed on majority ack from the CaseActor cluster.
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
- `specs/case-log-processing.md` — assertion recording and canonical
  `CaseLogEntry` requirements
- `plan/IMPLEMENTATION_PLAN.md` — SYNC-1 through SYNC-4 tasks
- `docs/adr/` — architectural decisions for CaseActor, per-actor DataLayer
- `notes/case-state-model.md` — CaseEvent model and trusted timestamps
