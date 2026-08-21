---
title: Sync Log Replication — Design Notes
status: active
description: "Design notes for sync log replication: append-only case activity log synchronization between actors."
related_specs:
  - specs/sync-ledger-replication.yaml
  - specs/case-ledger-processing.yaml
related_notes:
  - notes/case-ledger-authority.md
  - notes/case-state-model.md
relevant_packages:
  - vultron/core/behaviors
  - vultron/wire/as2
---

# Sync Log Replication — Design Notes

**Relates to**: `specs/sync-ledger-replication.yaml`

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
- **Single-node Raft framing**: The AppendOnlyLedger through PeerLedgerSync phases effectively
  implement a single-node Raft cluster. The CaseActor is permanently the
  leader (no election needed), and every append is an immediate commit. A
  single-node configuration MUST always be supported as the degenerate case
  of the general distributed model.
- **Two-tier replication**: Vultron has two distinct replication tiers that
  MUST NOT be conflated. (1) *CaseActor cluster replication* synchronizes
  multiple CaseActor instances for high-availability write authority — this
  is the scope of the Raft consensus protocol. (2) *Participant replication*
  delivers the canonical recorded log from the CaseActor cluster leader to
  Participant Actors for state convergence — this is the scope of AppendOnlyLedger–PeerLedgerSync.
  Both tiers share the same `Announce(CaseLedgerEntry)` wire format, but serve
  different purposes.
- **Forward compatibility**: The single-writer, single-node design explicitly
  preserves forward compatibility with a multi-node Raft cluster for
  high-availability failover. A future Phase 3 adds N-node CaseActor cluster
  support using standard Raft (static membership, log-completeness election,
  no priority tiebreaker). Failover semantics are out of scope for AppendOnlyLedger–PeerLedgerSync
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

## Canonical Serialization

**Critical constraint**: Before cryptographic signatures are added to log
entries (AppendOnlyLedger "PROD_ONLY" requirement), a **canonical serialization form**
MUST be established. Changing the serialization after entries are signed will
invalidate existing hash chains.

The canonical form must specify:

- **Deterministic key ordering**: JSON object keys must be sorted in a
  stable, well-defined order (e.g., lexicographic). Implementations MUST NOT
  rely on insertion-order key iteration.
- **Stable UTF-8 encoding**: All string values must use a single stable
  Unicode normalization form; surrogate pairs and alternate encodings of the
  same code point must be normalized.
- **Explicit field inclusion/exclusion**: The set of fields included in the
  hash computation must be precisely specified. Fields added later (e.g.,
  signature itself, performance-cache fields) MUST be excluded from the
  hashed content.
- **No whitespace variation**: The canonical byte string must have no
  optional whitespace; implementations using pretty-printing for storage
  MUST produce a compact form for hashing.

**Reference**: [RFC 8785 — JSON Canonicalization Scheme (JCS)](
https://www.rfc-editor.org/rfc/rfc8785) is the recommended standard. JCS
provides deterministic key ordering and Unicode normalization with
wide library support.

**Merkle Tree forward-compatibility**: The entries produced by this
serialization scheme will serve as leaf nodes of a future Merkle Tree. The
canonical form must be stable enough that leaf node hashes remain valid
when the chain is reorganised into a tree structure. See `SYNC-01-005`.

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
| AppendOnlyLedger | Local append-only log with hash-chain indexing            |
| LedgerFanout | One-way replication from CaseActor to Participant Actors  |
| LedgerReconciliation | Full sync loop with retry/backoff                         |
| PeerLedgerSync | Multi-peer synchronization (completes single-node CaseActor participant replication) |

### AppendOnlyLedger Scope

The canonical `CaseLedgerEntry` model (see `notes/case-ledger-authority.md`)
provides the foundation. AppendOnlyLedger extended it toward a true canonical recorded
log with hash-chain indexing; the richer long-term content model is described
in `notes/case-ledger-authority.md`.

Note: the earlier `CaseEvent` lightweight event model and
`VulnerabilityCase.record_event()` helper were removed in #792 once
canonical `CaseLedgerEntry` fully covered protocol-significant history.

Core domain classes (transport-agnostic):

- `CaseLedger` — append-only log; enforces immutability and hash-chain
- `ReplicationState` — per-peer last-acknowledged hash

`CaseLedgerEntry` fields for AppendOnlyLedger:

- `log_index` — monotonically increasing integer scoped to the case (MUST;
  see SYNC-01-002). Added in AppendOnlyLedger so downstream code and wire format are
  index-aware from the start.
- `term` — Raft term number (OPTIONAL in AppendOnlyLedger; defaults to `null` or `0`
  in single-node deployments; becomes required when multi-node CaseActor
  cluster is introduced in Phase 3).

Adapter responsibilities:

- AS2 `Announce` activity mapping (outbound replication message)
- Inbound handler for `Announce` (participant receiving a log entry)
- File/database log storage

### LedgerFanout Scope

One-way replication from CaseActor to each Participant Actor:

- Strict conflict handling: reject mismatched `prev_log_hash`, respond
  with last-accepted hash
- Sender retries from the entry following the reported last-accepted hash

Design Decision (blocks LedgerFanout): Reconcile "replication leadership" with
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

- In a **single-node** CaseActor (AppendOnlyLedger–PeerLedgerSync): every append is an immediate
  commit. There is no replication quorum to wait for.
- In a **multi-node CaseActor cluster** (Phase 3 Raft): an entry is committed
  once the leader has received acknowledgement from a majority of cluster
  peers. The leader only advances the commit index after majority ack.

**Emit-after-commit invariant**: External Vultron messages (activities sent
to Participant Actors or other protocol peers) MUST only be emitted after the
associated `CaseLedgerEntry` is committed. Participant replication fan-out
(`Announce(CaseLedgerEntry)`) is therefore always downstream of the commit index
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
   log position. This extends to projected protocol state:
   `ApplyParticipantStatusFromLedgerNode` will not let an entry move a
   replica's RM state backwards on the progress scale, even though the Case
   Actor is authoritative for *which* transition happened. A replayed,
   reordered, or divergent entry would otherwise un-see progress the replica
   has already observed. The local value is carried forward for `rm` only;
   every other dimension is applied as the entry describes it, and lateral
   moves at the same rank (`VALID` ↔ `INVALID`) are re-adjudication rather than
   regression (RSH-05-007, ADR-0061).

   The ratcheted status is saved to the DataLayer **unconditionally**. The node
   appends the object it reads *back* from the DataLayer — a wire-typed instance
   is required, because appending the core model to a
   `list[WireParticipantStatus]` makes Pydantic serialize it with the declared
   element type's defaults. So the ratchet only takes effect if the ratcheted
   copy is what got written. A status object can already be stored locally
   without being on the participant (an out-of-order `Announce` of the object
   itself, or a replayed entry), and skipping the save in that case appends the
   un-ratcheted status while the ratchet's own warning claims the local value was
   carried forward.
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
  mapped to distinct `MessageSemantics` values. `Announce(CaseLedgerEntry)` is
  the unified replication envelope for both CaseActor cluster AppendEntries
  and Participant Actor replication.
- **AS2 activity mapping**:

  | Raft function      | AS2 activity type                        |
  |--------------------|------------------------------------------|
  | AppendEntries      | `Announce(CaseLedgerEntry)`                 |
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
leader. This ensures that only the leader generates `CaseLedgerEntry` objects
and emits external Vultron activities.

Design approach:

- Add a **leadership role-check port** to the BT bridge
  (`vultron/core/behaviors/bridge.py`). The port is a simple callable or
  Protocol that returns `True` if the calling node is the current leader.
- In AppendOnlyLedger–PeerLedgerSync (single-node): the port implementation always returns `True`.
- In Phase 3 (multi-node): the port queries the Raft state machine.

This port SHOULD be added during AppendOnlyLedger so that the seam already exists in
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
  `PROD_ONLY` scope but SHOULD be designed before LedgerReconciliation to avoid
  retrofitting later.

---

## Fan-Out Graceful Degradation

`_fan_out_log_entry` (in `vultron/core/use_cases/triggers/sync.py`) queues one
`Announce(CaseLedgerEntry)` per peer participant. `sync_port` is an **optional**
injection: when it is absent (single-actor context, tests, or configurations
without a `SyncActivityAdapter`), the function logs at `DEBUG` level and
returns immediately instead of raising.

This differs from the two functions that **require** `sync_port`:

- `_send_rejection` — must be able to send a rejection; raises `VultronError`
  if `sync_port` is absent.
- `replay_missing_entries_trigger` — replaying entries to a peer requires an
  outbound channel; raises `VultronError` if `sync_port` is absent.

**Rule**: fan-out is optional behaviour — skipping it silently is correct when
no sync port is configured. Rejection and replay paths are not optional; they
MUST raise if the port is missing.

This means BT node tests and single-actor integration tests do **not** need a
`sync_port` injected on the blackboard or as a use-case parameter — the absence
is handled gracefully without patching.

---

## Ledger write ownership vs. message-ingress scratch (SYNC-13)

The SYNC-12 effects-before-persist gate (`CheckLedgerEntryAlreadyStoredNode`)
treats **presence of a `CaseLedgerEntry` in the DataLayer** as proof that the
entry's domain effects were already applied — so it skips the whole
`ProcessAndStore` subtree on repeat delivery. That inference is only sound if
the *only* writer of a `CaseLedgerEntry` is the core write path that also
applies the effects (`PersistReceivedLogEntry` for a participant replica; the
CaseActor's authoritative append for the primary case).

The FastAPI ingress adapter previously violated that: `_store_nested_inbox_object`
pre-stored the inline `CaseLedgerEntry` during parse so that `rehydrate()` —
which re-read the activity **by ID** from the DataLayer — could re-expand a
dehydrated `object_` for semantic routing. That single adapter write made the
gate fire SUCCESS on first delivery, so `LogEntryEventEffects` never ran (e.g.
`ApplyInviteAcceptFromLedger` never added a participant → FVV "participant
count 4; found 3"). Removing the pre-store instead broke routing, because a
bare-string `object_` matches both `AnnounceLogEntryPattern` and
`AnnounceVulnerabilityCasePattern` (both permissive). This is the
oscillation tracked across issues #1324, #1446, and #1472.

**Resolution (SYNC-13):** ledger writes are a core responsibility; ingress
delivers messages and never writes the ledger. Concretely:

1. `_store_nested_inbox_object` refuses to persist a `CaseLedgerEntry`
   (SYNC-13-002).
2. `FastAPIIngressAdapter.rehydrate` hydrates the **in-memory** parsed activity
   for an `Announce(CaseLedgerEntry)` (via `DataLayer.hydrate`) instead of
   re-reading it by ID, so the typed inline entry survives for routing without
   any pre-store (SYNC-13-003/004). Non-ledger activities keep the canonical
   by-ID read path unchanged.
3. Serialization preserves inline nested-object subtype fields end-to-end:
   `Record.from_obj`, the outbox delivery recovery map, and both wire emitters
   (`ASGIEmitter`, `DemoHttpDeliveryAdapter`) use `serialize_as_any=True`; the
   `CaseLedgerEntry` inside a stored `Announce` is kept inline rather than
   dehydrated to a bare ID (`_dehydrate_data`), and `Record.to_obj` re-types
   inline refs on read so replay reconstructs the full typed entry (#1472 AC-4).
4. The wire parser does not recurse into opaque data blobs
   (`payload_snapshot`); doing so coerced the snapshot into a typed activity and
   made `CaseLedgerEntry` validation fail, silently down-casting the entry to
   base `as_Object`.

Consequence for tests: a participant must already hold the case replica (with
its per-case genesis hash) before it can validate a replicated
`CaseLedgerEntry` (`ReconstructChainTail` anchors on the genesis hash,
CLP-08-005). Tests that previously relied on the adapter pre-store to make the
entry "appear" in the peer DL must seed the case on the peer instead.

---

## Out-of-Order Delivery and the Ledger Gap Buffer (SYNC-10-004)

`Announce(CaseLedgerEntry)` travels over a transport with **no ordering
guarantee**, and Vultron may not be the only protocol implementation on the
wire. A participant replica can therefore receive an entry before its
hash-chain predecessor. The bare reject-on-mismatch path
(`CheckHashOrRejectOnMismatchNode` → `SendRejectLogEntryNode`) *dropped* such an
entry and relied on a `Reject → replay` round-trip to redeliver it. That
recovery is itself order-fragile — `SendMissingEntriesNode` replays each missing
entry as a *separate* `Announce`, which can reorder again and hit the same drop
— so under adversarial reordering an entry could be lost indefinitely
(issue #1556, observed as Vendor2 stalling at case closure in the FVV demo).

**Resolution: receiver-side buffering makes convergence order-independent.**

- `LedgerGapBuffer` (`vultron/core/models/ledger_gap_buffer.py`) is an
  actor-local, per-case, in-memory store of forward-gap entries, mirroring
  `PendingAssertionStore`: per-actor module-level registry, ephemeral (lost on
  restart; the SYNC-10 catch-up gate re-syncs), **not** a DataLayer entity. This
  is the "clearly separate, non-ledger holding area" sanctioned by SYNC-13-003 —
  presence of a `CaseLedgerEntry` in the DataLayer still means "effects applied
  and entry committed" (SYNC-13-001).
- **Keyed on `prev_log_hash`** (the entry's upstream tooth). The successor of a
  just-persisted tail is exactly `buffer[new_tail.entry_hash]` — an O(1) lookup,
  so a contiguous buffered run of *k* entries drains in O(k). Keying on `id_`,
  `entry_hash`, or a plain list would make find-next O(n) and the cascade O(n²).
- **On mismatch:** if the entry is a genuine *forward* gap
  (`log_index > tail_index + 1`) it is buffered; a `Reject(CaseLedgerEntry)` is
  **still always sent** as the backstop for entries that are genuinely *lost*
  (never delivered) rather than merely reordered. Stale/at-or-behind-tail
  entries are not buffered — they fall straight through to the reject.
- **On commit:** `AnnounceLedgerEntryReceivedUseCase` drains the buffer — for
  each newly committed tail it re-runs the announce receive BT on the buffered
  successor, reusing the exact effects-before-persist path (SYNC-12-001) and
  cascading until no buffered entry extends the tail.
- **Bounded:** the buffer caps per-case size and evicts the entry farthest ahead
  of the gap (highest `log_index`) with a WARNING; eviction is recoverable via
  the Reject already sent, so it never has to re-trigger recovery itself.

Because replayed entries flow through the *same* receive path, buffering also
makes the `Reject → replay` recovery order-robust for free — no separate
redesign of the replay loop was needed. A companion fix made
`SyncActivityAdapter.send_reject_log_entry` enqueue against the explicit
receiving `actor_id` (via `add_activity_to_outbox` / `record_outbox_item`)
instead of the DL's own scope (`outbox_append`), matching
`send_announce_log_entry` so a reject is delivered correctly even from a
shared/differently-scoped DataLayer.

## Pre-SYNC-13 Upgrade Path

Nodes that ran pre-SYNC-13 code may hold stale `{entry: stored, effects: not-applied}`
state. This arises because `_store_nested_inbox_object` formerly persisted a
`CaseLedgerEntry` during parse without applying the entry's domain effects. When such
a node later receives the same `Announce(CaseLedgerEntry)`, `CheckLedgerEntryAlreadyStoredNode`
(SYNC-12-003) fires SUCCESS and the entire `ProcessAndStore` subtree — including
`LogEntryEventEffects` — is skipped. The entry's effects are never applied, and the
node's derived state (e.g., participant list, EM state) remains stale.

**Resolution: Accept.** No repair path is implemented. The pre-SYNC-13 code was a
bug in pre-production code with no extant deployed nodes or cases. The correct recovery
for any node in this state is to wipe its local DataLayer for the affected case and
re-sync from the CaseActor. Re-sync replays all `Announce(CaseLedgerEntry)` entries
from the beginning; each entry passes the `CheckLedgerEntryAlreadyStoredNode` gate
(FAILURE — not yet stored), so `ProcessAndStore` runs and effects are applied correctly.

This is tracked as issue #1446.

## Genesis-Unavailable Buffer-and-Reject (SYNC-15)

`Announce(CaseLedgerEntry)` can arrive at a participant replica before
`Create(VulnerabilityCase)` has been processed (a delivery-order race under HTTP
BackgroundTasks). When that happens, `ReconstructChainTailNode` cannot derive the
per-case genesis hash (CLP-08-005) and returns FAILURE.

**Before the fix (issue #1873)**: FAILURE from `ReconstructChainTailNode` exited
the `ProcessAndStore` Sequence without reaching `CheckHashOrRejectOnMismatchNode`,
so no `Reject(CaseLedgerEntry)` was sent. The CaseActor never learned about the
failure and never replayed the entry → permanent data loss on the replica.

**After the fix**: `ReconstructChainTailNode` writes sentinel values
(`tail_hash=""`, `tail_index=-1`) before returning FAILURE. The announce tree
wraps the node in a Selector whose fallback is `SendRejectLogEntryNode`, so the
Reject fires even when chain reconstruction fails. The Reject carries
`last_accepted_hash=""` (meaning "I have no entries; replay from genesis") so
the CaseActor re-announces all entries once the case is delivered.

**Implementation**: `vultron/core/behaviors/sync/nodes/chain.py`
(`ReconstructChainTailNode.update`) and
`vultron/core/behaviors/sync/announce_tree.py` (`ReconstructOrRejectOnMissingCase`
Selector). Spec: SYNC-15-001, SYNC-15-002. Regression test:
`test/core/use_cases/received/test_sync.py::TestAnnounceLedgerEntryReceivedUseCase
::test_missing_case_queues_reject_with_empty_tail_hash`.

### Pre-Genesis Buffering and Drain on Case Seed (SYNC-15-004/005)

The Reject backstop above is *loss* recovery — it depends on the CaseActor
re-announcing entries once the case lands, over the same unordered transport,
so each pre-genesis entry Rejects again and amplifies CLP-08-005 churn (#2169).
Worse, in the `fcvcv` V1 demo the dropped `add_report_to_case` entry meant no
`VultronOfferRecord` was ever created and the report offer 404'd (#2180). The
forward-gap buffer (SYNC-10-004 above) does **not** catch this: its
`log_index > tail_index + 1` test never fires when there is no chain at all, so
a pre-genesis entry falls straight through to the reject-on-missing-case path.

**Resolution (ADR-0059, #2186): buffer pre-genesis entries and drain on case
seed.** The per-case genesis hash is deterministic from the case object alone
(`compute_genesis_hash` runs at `VulnerabilityCase` construction when
`attributed_to` is present, CLP-08), so seeding the case is sufficient to anchor
the chain — no need to wait for the genesis ledger entry to be re-delivered.

- `BufferPreGenesisEntryNode`
  (`vultron/core/behaviors/sync/nodes/receive.py`) is wired as the first child
  of the `ReconstructOrRejectOnMissingCase` fallback, wrapped in
  `FailureIsSuccess` so the genesis `Reject` still fires as the loss backstop.
  Unlike `BufferOutOfOrderEntryNode` it applies **no** forward-gap check — there
  is no tail in the pre-genesis window, so every entry for the missing case is
  held in the same `LedgerGapBuffer`.
- The ADR-0037 drain is extracted to a module-level
  `drain_gap_buffer(...)` (`vultron/core/use_cases/received/sync.py`) reused by
  both the announce receive path and a new drain-on-seed hook in
  `AnnounceVulnerabilityCaseReceivedUseCase`. In the pre-genesis case the first
  reconstructed tail is `(genesis_hash, -1)`, so a buffered genesis entry
  (`prev_log_hash == genesis_hash`) drains first and the rest cascade in
  hash-chain order, reusing the exact effects-before-persist path (SYNC-12-001).
- `ANNOUNCE_VULNERABILITY_CASE` was added to `_SYNC_PORT_SEMANTICS` so the seed
  use case receives the `sync_port` the drain needs to send a Reject on any
  residual mismatch.

Spec: SYNC-15-004 (buffer pre-genesis), SYNC-15-005 (drain on seed).
ADR: `docs/adr/0059-buffer-pre-genesis-ledger-entries.md`. Regression tests:
`test/core/use_cases/received/test_sync.py::TestPreGenesisAnnounceBuffering` and
`test/core/use_cases/received/actor/test_announce.py::TestAnnounceDrainsPreGenesisBuffer`.

## Reject/Replay Amplification (SYNC-15-003)

The Reject → replay backstop above is a *recovery* mechanism, and recovery paths
that fire unconditionally can amplify. `SendMissingEntriesNode` originally
replayed the whole missing suffix on every `Reject(CaseLedgerEntry)`, with no
convergence check. A peer that cannot anchor its hash chain — typically a late
joiner — Rejects *every* entry replayed to it, so each Reject triggered a
full-ledger replay and each replayed entry triggered another Reject: a
self-sustaining loop.

Observed in the `fcvcv` demo (issue #1989): **4825** `Announce(CaseLedgerEntry)`
activities for a single 26-entry case (~185x amplification), 4201 of them aimed at
one late-joining actor, at a steady ~2 replays/sec of the same 25-entry ledger with
zero progress between rounds. The event storm starved the containers until
*unrelated* DataLayer reads failed with `ReadTimeout`, which surfaced as misleading
`"replica matches authoritative state: timed out"` demo failures. This is also the
mechanism behind the flakiness that rotated across `fvcv-extension` /
`fvcv-handoff` / `fccv-extension` on unrelated branches (#1839, #1911) — the
reject/replay path is shared code, so any scenario could trip it under CI load.

Note the existing genesis guard (`AnnounceCaseOnGenesisRejectNode`, SYNC-15-002)
did not cover this: it only handles `last_accepted_hash == ""`, and a peer stuck at
a *non-empty* hash falls straight through it.

**Resolution**: `vultron/core/behaviors/sync/nodes/replay_guard.py` bounds the
replay *rate* per peer. `VultronReplicationState` gained
`last_replayed_from_hash` / `last_replayed_at`, and the node asks
`should_replay()` before replaying, then calls `record_replay()` after.

Three properties are load-bearing, and each has a regression test:

- **Rate limit, not suppression.** A Reject at an unchanged position is
  rate-limited (30s), never permanently blocked — if a replayed entry is lost in
  transit, a later Reject must still be able to trigger a fresh replay or the peer
  never converges.
- **Ask and record are separate steps.** The position is recorded only once at
  least one entry has actually gone out. Recording at decision time meant a peer
  already at the ledger tail (zero entries to send) started a cooldown anyway; when
  the ledger then grew, that peer's next Reject — reporting the same hash, now
  genuinely stale — was suppressed, so it waited out the cooldown having received
  nothing. That is the very stall the guard exists to prevent, reintroduced by the
  guard.
- **Genesis gets a short cooldown, not an exemption.** Genesis convergence is owned
  by SYNC-15-001/002, which seed the case and rely on the *following* replay to
  deliver history; a full-length cooldown there starved the bootstrap (caught by
  `fccv-handoff` in CI: 34 suppressions against a Finder stuck at genesis, ending in
  "LedgerFanout replication did not complete"). Exempting genesis outright would re-admit
  the storm, since a peer that cannot anchor reports genesis on every Reject — 43 of
  51 suppressions in the fixed `fcvcv` run were at genesis. So: 2s, not 0s and not
  30s.

The guard lives in its own module rather than in `replay.py` to keep that leaf
module under the 500-line BTND-07-004 limit.

Spec: SYNC-15-003. Regression tests:
`test/core/behaviors/sync/nodes/test_replay_guard.py` (unit) and
`test/core/behaviors/sync/test_reject_tree.py` (through the tree — the loop
reproduced there as 240 replays where 24 were correct). These run in-process in
seconds rather than requiring a 20-minute demo-integration cycle (#1970).

## Document Boundary: Internal Spec vs. External Companion

This file and `specs/sync-ledger-replication.yaml` are the **internal**
implementation references for the ledger replication protocol.

A separate **external-facing companion document** (suitable for reviewers
outside the project alongside the main Vultron protocol RFC) covers the same
protocol mechanics — see `docs/reference/draft-vultron-replication-spec.md`
(tracked in issue #2495).

The external companion and the internal SYNC spec cover the same protocol but
serve different audiences. When the SYNC spec requirements change, the companion
document MUST be updated to stay consistent. Normative requirements always
originate in `specs/sync-ledger-replication.yaml`; the companion document is a
reader-friendly rendering, not an independent source of truth.

The document-boundary decision — why the replication mechanics live in a
companion document rather than the main RFC — is recorded in
`docs/adr/0069-ledger-replication-companion-spec.md` (tracked in issue #2494).

## Related

- `specs/sync-ledger-replication.yaml` — normative requirements
- `specs/case-ledger-processing.yaml` — assertion recording and canonical
  `CaseLedgerEntry` requirements
- `docs/adr/` — architectural decisions for CaseActor, per-actor DataLayer
- `notes/case-state-model.md` — CaseStatus append-only history and state model
