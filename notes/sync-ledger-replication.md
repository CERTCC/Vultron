---
title: Sync Log Replication — Design Notes
status: active
kind: guidance
description: >
  Rules for replicating the canonical case ledger to participants: single-writer
  log, hash-chain sync, canonical serialization, commit and replica invariants,
  the sync-port wiring rule, fan-out recipients and the embargo pause, ingress
  never writing the ledger, the held out-of-order Announce, divergence recovery,
  replay rate limiting, and SYNC test patterns.
related_specs:
  - specs/sync-ledger-replication.yaml
  - specs/case-ledger-processing.yaml
  - specs/case-proposal.yaml
  - specs/case-management.yaml
  - specs/behavior-tree-integration.yaml
  - specs/participant-case-replica.yaml
  - specs/protocol-asks.yaml
  - specs/received-status-handling.yaml
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

- **A receiver checks an entry's own hash before its place in the chain**
  (SYNC-03-006). The predecessor check proves position, not content. Build the
  stored entry with `HashChainLedgerRecord.to_ledger_entry()` and check one with
  `ledger_entry_hash_intact()`, never a hand-built `CaseLedgerEntry`: hashed
  fields such as `received_at` then default to a fresh clock (#3744).
- **One hash predicate, wherever an entry is checked.** The receiver's check, the
  CASE_MANAGER's check of its own copy on a hash-mismatch fault, and any send-side
  check all call `ledger_entry_hash_intact()`. A second copy of the hashing logic
  can disagree with the first and blame the wrong side (SYNC-03-008, #5095).
- **A hash refusal is reported, not recovered.** The replica sends
  `LedgerEntryRefused/HashMismatch`; the CASE_MANAGER logs it at ERROR and checks its
  own copy, and does nothing else. Replay and re-seed resend the same content, so
  neither can repair it; the replay cooldown bounds the loop (SYNC-03-007/008).

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
   position. It copies each status an entry carries, id, times and every
   dimension as carried, and carries no local value over it (CM-23-016): the
   CASE_MANAGER never commits a regression, so a ratchet would only make a
   diverged replica disagree further.
   - An entry whose composite state violates the RM↔VF, RM↔D or VF↔D entailments
     is not applied; the replica emits `Create(ProcessingFault)`
     `StatusAssertionRefused/ImpossibleState` to the CASE_MANAGER (RSH-09-006).
   - The carried status is saved even when an object with its id is already
     stored, so the CASE_MANAGER's copy replaces one a trigger stored without
     attaching it (RSH-08-006).
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

1. Ingress stores no inline object (CLP-10-017), and `_stage_inline_object`
   does not stage a `CaseLedgerEntry` even in the throwaway routing store
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

## Out-of-Order Delivery and the Held Ledger Announce (SYNC-10-004)

The transport promises no order, and other implementations may share the wire,
so a replica can get an entry before its predecessor. One drain per actor with
per-recipient lanes (ADR-0112, OX-01-004/005/006) makes this rare, and a replay
does not re-queue an `Announce` the outbox already holds for that peer
(SYNC-15-012). The hold below is the backstop for loss, not the steady state.

- **Hold the Announce, never the entry alone** (SYNC-14-001). The body intake
  archived is held in a `DeferredInboxActivity`, the inbox's replay record
  (IO-03-004); a `HeldLedgerAnnounce` row indexes it. Reason: an entry held alone
  can only reach the inbox again inside an Announce the replica makes up and
  attributes to the CASE_MANAGER (ISSUE-5012). Both live in the receiver's store,
  never as a `CaseLedgerEntry` (SYNC-14-005), so a restart keeps them.
- **Keyed on `prev_log_hash`**, so the successor of a new tail is one read
  (`HeldLedgerAnnounce.build_id(case_id, tail_hash)`). The operations live in
  `vultron/core/services/held_ledger_announces.py`.
- **On mismatch**, a genuine forward gap (`log_index > tail_index + 1`) is held,
  and a `Reject(CaseLedgerEntry)` is **still always sent** as the loss backstop.
  At-or-behind-tail entries go straight to the reject.
- **On commit**, `ReplayHeldSuccessorNode` (`sync/nodes/replay_held.py`, last in
  the participant arm, and after the seed in the case-Announce tree) asks
  `InboxReplayPort` to replay the one held Announce that extends the new tail,
  by its own id (SYNC-14-009). That delivery's tree replays the next, so the
  cascade needs no loop and runs the in-order path by construction
  (SYNC-14-008). Reason: running the successor inline made one delivery run
  several trees (CLP-10-005, ADR-0135).
- **The adapter queues, it never processes.** `InboxReplayAdapter` checks the
  body is held and calls `inbox_append`; the inbox loop pops it afterwards and
  replays it through `process_payload` under the same actor lock, parsed again
  from the held body, so it carries the first delivery's evidence and intake
  archives nothing new. A missing port is a `VultronWiringError`, never an inline
  apply.
- **Replay only after success.** The node runs after the entry is stored (or
  found stored), never on a refusal: an entry refused and held is keyed on the
  current tail, so replaying on failure would loop it into itself.
- **Bounded** (SYNC-14-006): a full holding area drops the Announce farthest
  ahead, body and all, with a WARNING; the Reject already sent recovers it.

Enqueuing for another actor means opening that actor's store explicitly
(`store_for_actor`, DL-07-005) and calling `outbox_append` on it.

## A Refusal That Extends the Chain Is Divergence (SYNC-16)

When the apply function refuses an entry whose predecessor the replica holds, no
replay can help: the replica's case file has diverged, and the replay resends the
same entry forever (ADR-0142).

- **Report it, never patch it.** The replica sends `Create(ProcessingFault)`
  `LedgerEntryRefused/CaseDiverged` and keeps holding the entry; the CASE_MANAGER
  answers an active participant with a fresh `Announce(VulnerabilityCase)`.
- **Never ledger it.** A fault about applying an entry is replication signalling,
  like the gap Reject; the replica that sent it could not apply its entry
  (SYNC-16-002).
- **A case stores the ledger position it is a projection of.** Only
  `store_ledger_entry()` moves it, in the transaction that stores the entry, on
  every commit and replica store. A node that saves or snapshots a case it read
  before committing passes it through `at_stored_position()` first, or the save
  puts the position back and the snapshot names a stale one (SYNC-16-005).
- **A position never moves back.** Storing an entry at or before the case's
  position leaves the position where it is: a replica seeded ahead of its chain
  stores the replayed entries as no-ops, and moving back would make the next
  copy look ahead again (SYNC-16-007).
- **A case copy is judged by the position it names.** Chain already past it:
  stale, `SKIPPED`, because an old copy can arrive late. A different entry at its
  index: `REFUSED` at ERROR. Otherwise the copy replaces the case, position
  included (SYNC-16-006). The repeat-Announce path (MV-10-004) takes the same
  judgement, never a whole replace (`services/case_copy.py`).
- **A copy carries each record as the store holds it now.** `_case_for_wire`
  re-reads a participant or report the case holds inline, because a current
  copy replaces the replica's records unconditionally; a stale inline snapshot
  regressed a replica's RM (#4797). The CASE_MANAGER skips a copy of its own,
  as it receives its broadcast as a participant: its case is the source.
- **Replace in one transaction.** `SeedAnnouncedCaseNode` writes the
  participants, reports and the case at the copy's position together (ADR-0146);
  a split write could leave a replaced case whose reflected entries are applied
  again.
- **An entry the copy reflects is gated once, before every apply node.**
  `EntryReflectedByCaseCopyNode` stores an entry at or before
  `case.ledger_position` without effects, so no apply node needs its own "copy is
  past" test; `case_file_is_past()` stays for the embargo register's own replays.
  That includes the held refused entry, which the seed drains before any replay
  arrives, and the backfill after a join seed (SYNC-16-007).
- **An empty chain still asks.** A replica with no stored entry sends the `Reject`
  that names none: empty last-accepted hash, case as `target`. The parser admits an
  objectless `Reject` only in that form (`ledger_reject_envelope.py`), and the
  CASE_MANAGER reads the case through `rejected_case_id`, never the entry.
- **A no-op still copies what the copy names by id.** A copy carries participants,
  reports and the active embargo inline but names notes, statuses and other
  embargoes by id; `StoreRecordsReflectedEntryCarriesNode` stores those records
  from the reflected entry, or the replica ends short of seed-plus-replay
  (CM-23-016, #5052).
- **Divergence is a starting-state mismatch, not invalid content.** An entry that is
  wrong in itself, like an impossible participant status, takes RSH-09-006's fault:
  a fresh copy cannot repair it (SYNC-16-001).

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
own hold, in the same holding area (ADR-0059):

- `BufferPreGenesisEntryNode` (`sync/nodes/receive.py`) is the first child of the
  `ReconstructOrRejectOnMissingCase` fallback, under `FailureIsSuccess` so the
  genesis Reject still fires. It applies no forward-gap check.
- Seeding the case is enough to anchor the chain, because the genesis hash comes
  from the case object alone (CLP-08). The `Announce(VulnerabilityCase)` tree ends
  in the same `ReplayHeldSuccessorNode` the announce path uses, which finds the
  Announce keyed on the genesis hash and replays it (SYNC-15-005, SYNC-14-009).

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
- **The cooldown doubles per no-progress replay, capped at 600 s** (SYNC-15-013).
  A fixed one stops the loop only when a round trip beats it, so a slow host
  livelocks; `replays_at_position` resets on progress (#4882).
- **The genesis case pre-seed follows the replay decision** (SYNC-15-014): an
  unguarded pre-seed sends one case per Reject inside a suppressed window.
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
