---
title: Sync Log Replication — Design Notes
status: active
kind: guidance
description: >
  Rules for replicating the canonical case ledger to participants: single-writer
  log, hash-chain sync, canonical serialization, commit and replica invariants,
  the sync-port wiring rule, fan-out recipients and the embargo pause, ingress
  never writing the ledger, the gap and pre-genesis buffers, replay rate limiting,
  and SYNC test patterns.
related_specs:
  - specs/sync-ledger-replication.yaml
  - specs/case-ledger-processing.yaml
  - specs/case-proposal.yaml
  - specs/case-management.yaml
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/case-ledger-authority.md
  - notes/case-actor-cluster.md
  - notes/case-ledger-parsing.md
  - notes/outbox-delivery-reliability.md
  - notes/flaky-tests.md
  - notes/case-state-model.md
  - notes/message-type-reference.md
  - notes/testing-pitfalls.md
  - notes/participant-embargo-consent.md
  - notes/case-joining.md
  - notes/core-wire-rendering-port.md
  - notes/bt-pitfalls.md
  - notes/case-communication-model.md
  - notes/participant-case-replica.md
  - notes/demo-ci-diagnostics.md
relevant_packages:
  - vultron/core/behaviors
  - vultron/wire/as2
---

# Sync Log Replication — Design Notes

Normative requirements: `specs/sync-ledger-replication.yaml` (SYNC). Multi-node
CaseActor clustering is unbuilt; its plan is
[case-actor-cluster.md](case-actor-cluster.md).

## Architecture Overview

- **Single writer.** The CASE_MANAGER alone appends to the hash-chained canonical
  log; all replicated state is a deterministic projection of it. This is a
  single-node Raft cluster: always the leader, every append an immediate commit.
  Do not assume failover semantics anywhere in the participant-replication code.
- **Eventual consistency.** Participants converge by applying replicated
  entries.
- **Only admitted entries are replicated.** Refusals go to the asserter and the
  process log, never the ledger (CLP-04-007, CLP-05-002), so replication needs no
  disposition filtering.
- **Leadership guard.** The BT bridge's `is_leader` port (SYNC-09-003,
  `vultron/core/behaviors/bridge.py`) is always `True` in single-node; it is the
  seam the cluster plan fills.
- **Leadership is not ownership.** Case Ownership governs lifecycle permissions;
  replication leadership governs who accepts writes. An ownership transfer
  implies a leadership change, not the reverse.

## Hash-Chain Design

Each entry carries a hash of its own content and its predecessor's hash. Sync
position is reported as a hash, not an index: a hash is self-verifying, and it
survives renumbering after compaction or migration. The CASE_MANAGER replays
everything after the last hash a participant reports.

## Canonical Serialization

The hashed form must be fixed **before** entries are signed; changing it later
invalidates every chain. It needs deterministic key order, one stable Unicode
normalization, an explicit field set (signatures and cache fields excluded), and
no optional whitespace. [RFC 8785 (JCS)](https://www.rfc-editor.org/rfc/rfc8785)
is the target; the gap between it and the current serializer is #3659. Leaf
hashes must stay valid if the chain later becomes a Merkle tree (SYNC-01-005).

## Log Position in Activity Context

A participant SHOULD put the hash of its last accepted entry in the `context` of
every message to the CASE_MANAGER, so the CASE_MANAGER can replay missing entries
without waiting for a sync request.

## Commit Discipline

An entry is **committed** once durably appended; in single-node every append
commits. **Emit after commit**: external messages, including the participant
fan-out `Announce(CaseLedgerEntry)`, go out only after their entry is committed,
so an act a node claims cannot be rolled back.

Invariants every component touching state, messaging or storage must preserve:

1. **Append-only integrity**: committed entries are immutable, identified by
   content hash.
2. **Deterministic projection**: the same log prefix yields the same state.
3. **Idempotent replay**: reprocessing any prefix, duplicates included, changes
   nothing.
4. **Monotonic visibility**: a replica never regresses its acknowledged
   position, and `ApplyParticipantStatusFromLedgerNode` never moves a replica's
   `rm` backwards on the progress scale. Only `rm` is ratcheted; same-rank moves
   (`VALID` ↔ `INVALID`) are re-adjudication, not regression (RSH-05-007).
   - An entry whose composite state violates the RM↔VF, RM↔D or VF↔D entailments
     is not applied; the replica emits `Create(ProcessingFault)`
     `StatusAssertionRefused/ImpossibleState` (or `.../CorruptLocalRecord` for an
     unreadable local record) to the CASE_MANAGER (RSH-05-021).
   - The ratcheted status is saved **unconditionally**, and the node appends the
     wire-typed object it reads back. Skipping the save when the status object is
     already stored appends the un-ratcheted value.
5. **Reject on divergence**: an entry that does not extend the chain is rejected
   and triggers resynchronization.

## A Missing Sync Port Is a Wiring Fault

`SendLogEntryToEachNode` (`sync/nodes/fanout.py`), the reject sender and the
replay sender raise `VultronWiringError` when `/sync_port` is absent, and
`RequireSyncPortNode` (`port_guard.py`) raises before any entry is minted. A
committed entry that is never announced breaks SYNC-02-003; skipping and
reporting success masks a delivery failure (BT-14-001, #4113).

**Rule**: wherever a ledger commit can run, the sync port must reach it.

- The inbox dispatcher gives every semantic the port via
  `with_received_baseline_ports()` (`inbox_port_factories.py`).
- Every received use case passes it to the `BTBridge` constructor, never as an
  `execute_with_setup` kwarg
  (`test/architecture/test_received_use_cases_fan_out_commits.py`).
- Tests that reach a commit inject `SyncActivityAdapter(dl)`, or
  `MagicMock(spec=SyncActivityPort)` when not about fan-out. `BTTestScenario`
  injects the real adapter.

A missing port inside a nested commit is re-raised by `CommitCaseLedgerEntryNode`
as `VultronBTInternalError`, so the handler raises instead of reporting `REFUSED`
(ADR-0095). See [bt-pitfalls.md](bt-pitfalls.md) § "…And That Idiom Is Why
`internal_error` Cannot See a Nested Crash".

## Fan-Out Recipients and the Embargo Gate (CM-10-005, CM-10-006)

Every sender of ledger entries (the fan-out collectors, `SendMissingEntriesNode`,
`AnnounceCaseOnGenesisRejectNode`) applies the CM-10-004 content gate through
`vultron/core/participants/recipients.py` (`case_content_recipients()`,
`is_case_content_recipient()`; CM-10-007). A peer that is not an active
participant gets no entries, and its `Reject(CaseLedgerEntry)` replays nothing
and seeds no case.

- **The reject tree checks the sender first** (`SenderIsActiveLedgerParticipantNode`,
  SYNC-03-005, ADR-0115) and answers `REFUSED` before writing replication state;
  the replay and pre-seed gates are defence in depth.
- **A closed peer keeps this one act**: the use case declares `LEDGER_PEER`, not
  `ACTIVE_PARTICIPANT`, because every `ACTIVE_PARTICIPANT` guard refuses a sender
  at RM `CLOSED` (CM-23-018). Its replay stops at its own closure entries
  (`closed_participant_ledger_cutoff()`, CM-23-004).
- **Answering a Reject is the CASE_MANAGER's act alone.** Replication state,
  pre-seed and replay sit in the reject tree's `manager_effects`, in that order,
  behind the factory gate (BT-17-008). A pre-seed whose gate is undecidable fails
  the tree before the replay rather than reading as a skip.
- **Only a joined, inactive participant is paused**: one the active embargo
  withholds, or one the Case Owner removed (CM-31-001).
  `inactive_joined_participants()` names them and the collectors publish them as
  `fanout_withheld`. A participant that has not joined is inert and gets its case
  through the join path (ADR-0114); no pause record is created for it.
- **The pause** is `VultronReplicationState.embargo_paused_from_index`, the first
  withheld `log_index`; a later withheld entry keeps the earlier index. Helpers:
  `sync/nodes/embargo_pause.py`.
- **On admission** the participant is backfilled in log order from that index
  through `send_ledger_suffix()` (the replay's own sender), and the pause cleared.
  A backfill sends entries only, never the case; a participant paused from 0
  buffers it (SYNC-15-004) and its genesis Reject gets the case seeded
  (SYNC-15-002).

Admission is caught at two points:

- **At fan-out.** `SendLogEntryToEachNode` backfills every admitted paused peer up
  to the entry it is sending, covering paths that change state first and commit
  after (for example `terminate_embargo_bt` then `EmitCaseStatusUpdateNode`). It
  recomputes the gate over the whole case, so a closed withheld peer is never read
  as admitted.
- **After an admitting received effect.** A received activity commits and fans out
  *before* its effect admits anyone (CLP-10-006), so
  `BackfillAdmittedParticipantsNode` (`embargo_admission_backfill_nodes()`) runs
  after the effect: accepted Invite, `Remove(EmbargoEvent)` teardown, an honored
  late Accept (EMB-17-001), and the owner's `Accept(EmbargoEvent, target=Case)`
  activating a revision a paused participant already accepted.

An admitted peer's own Reject clears the pause too: its replay resends everything
past its contiguous prefix (SYNC-10-004), and duplicates are idempotent
(SYNC-12-003). Why the gate pauses a whole stream is in
[participant-embargo-consent.md](participant-embargo-consent.md) § "Embargo
Messages Reach Non-Signatories".

## Ingress Never Writes the Ledger (SYNC-13)

`CheckLedgerEntryAlreadyStoredNode` (SYNC-12) treats a stored `CaseLedgerEntry`
as proof its effects were applied and skips `ProcessAndStore`. That is sound only
if the core write path that applies effects is the sole writer. So:

1. `_store_nested_inbox_object` refuses to persist a `CaseLedgerEntry`
   (SYNC-13-002). An adapter pre-store makes the gate skip effects on first
   delivery.
2. `FastAPIIngressAdapter.rehydrate` hydrates the in-memory `Announce(CaseLedgerEntry)`
   instead of re-reading it by id, so the inline entry survives for routing
   (SYNC-13-003/004). A bare-string `object_` would match both permissive
   Announce patterns.
3. Inline nested subtypes survive serialization end to end
   (`serialize_as_any=True`; the entry inside a stored `Announce` stays inline in
   `_dehydrate_data`).
4. The wire parser never recurses into `payload_snapshot`; coercing it into a
   typed activity down-casts the entry to `as_Object`.

For tests: a participant must hold the case replica (with its genesis hash)
before it can validate a replicated entry (CLP-08-005). Seed the case on the
peer; never rely on a pre-stored entry.

## Out-of-Order Delivery and the Ledger Gap Buffer (SYNC-10-004)

The transport promises no order, and other implementations may share the wire,
so a replica can get an entry before its predecessor. One drain per actor with
per-recipient lanes (ADR-0112, OX-01-004/005/006) makes this rare, and a replay
does not re-queue an `Announce` the outbox already holds for that peer
(SYNC-15-012). The buffer below is the backstop for loss, not the steady state.

- `LedgerGapBuffer` (`vultron/core/models/ledger_gap_buffer.py`) is actor-local,
  per-case and in-memory, **not** a DataLayer entity (SYNC-13-003). It is lost on
  restart; dropped entries come back through diverge/reject/replay (SYNC-14-002).
- **Keyed on `prev_log_hash`**, so the successor of a new tail is an O(1) lookup
  and a run of *k* entries drains in O(k).
- **On mismatch**, a genuine forward gap (`log_index > tail_index + 1`) is
  buffered, and a `Reject(CaseLedgerEntry)` is **still always sent** as the loss
  backstop. At-or-behind-tail entries go straight to the reject.
- **On commit**, `AnnounceLedgerEntryReceivedUseCase` drains the buffer through
  the same effects-before-persist path (SYNC-12-001), cascading.
- **Bounded**: a full buffer evicts the entry farthest ahead with a WARNING; the
  Reject already sent recovers it.

Enqueuing for another actor means opening that actor's store explicitly
(`store_for_actor`, DL-07-005) and calling `outbox_append` on it.

## Genesis-Unavailable Buffer-and-Reject (SYNC-15)

An entry can arrive before the case is seeded, so `ReconstructChainTailNode`
cannot derive the genesis hash (CLP-08-005). Both case-creation trees emit the
case seed first (CP-09-009, CM-17-009), so this is recovery, not the steady state.

- `ReconstructChainTailNode` writes sentinels (`tail_hash=""`, `tail_index=-1`)
  before FAILURE, and the `ReconstructOrRejectOnMissingCase` Selector in
  `announce_tree.py` falls back to `SendRejectLogEntryNode`, so a Reject with
  `last_accepted_hash=""` ("replay from genesis") always goes out (SYNC-15-001/002).
  Without it the CASE_MANAGER never learns of the failure.

### Pre-Genesis Buffering and Drain on Case Seed (SYNC-15-004/005)

The forward-gap test never fires with no chain, so pre-genesis entries need their
own buffer (ADR-0059):

- `BufferPreGenesisEntryNode` (`sync/nodes/receive.py`) is the first child of the
  `ReconstructOrRejectOnMissingCase` fallback, under `FailureIsSuccess` so the
  genesis Reject still fires. It applies no forward-gap check.
- Seeding the case is enough to anchor the chain, because the genesis hash comes
  from the case object alone (CLP-08). `drain_gap_buffer(...)`
  (`vultron/core/use_cases/received/sync.py`) is shared by the announce path and
  the drain-on-seed hook in `AnnounceVulnerabilityCaseReceivedUseCase`, starting
  from tail `(genesis_hash, -1)`.

## Reject/Replay Amplification (SYNC-15-003)

A peer that cannot anchor its chain Rejects every replayed entry, so unconditional
replay is a self-sustaining storm that starves unrelated work. The guard in
`vultron/core/behaviors/sync/nodes/replay_guard.py` (`should_replay()` then
`record_replay()`, state on `VultronReplicationState`) bounds replay rate per
peer. Three properties are load-bearing; tests are in
`test/core/behaviors/sync/nodes/test_replay_guard.py` and
`test/core/behaviors/sync/test_reject_tree.py`:

- **Rate limit, not suppression** (30 s at an unchanged position). A permanent
  block would strand a peer whose replayed entry was lost.
- **Ask and record are separate.** Record only after at least one entry went
  out; recording a zero-entry decision suppresses the peer's next, genuinely
  stale Reject once the ledger grows.
- **Genesis gets a short cooldown (2 s), not an exemption.** A long cooldown
  starves bootstrap (SYNC-15-001/002 rely on the following replay); an exemption
  readmits the storm, since an unanchored peer reports genesis every time.

## Document Boundary: Internal Spec vs. External Companion

`specs/sync-ledger-replication.yaml` is normative.
`docs/reference/draft-vultron-replication-spec.md` is the external companion
rendering of the same protocol (ADR-0077). When a SYNC requirement changes, update
the companion in the same change.

## SYNC Replication Test Patterns

- **Happy path (SYNC-901).** Two `create_isolated_actor_app` instances plus a
  shared `_TestClientRouter` emitter fallback, which POSTs to each app's
  `TestClient` inbox (the only sanctioned in-process transport, ADR-0042 /
  OX-12-003; no hand-rolled `httpx.ASGITransport`). Use `post_actor_inbox` for
  inbound activities.
- **Predecessor mismatch (SYNC-902).** Do not inject via `post_actor_inbox`:
  `CheckLedgerEntryAlreadyStoredNode` can short-circuit before hash validation.
  Call `handle_inbox_item(dl, activity)` directly, then drive outbox replay from
  the CASE_MANAGER.
