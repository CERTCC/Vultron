---
title: Sync Log Replication — Design Notes
status: active
kind: guidance
description: >
  Rules for replicating the canonical case ledger to participants: single-writer
  log, hash-chain sync, canonical serialization, commit and replica invariants,
  the sync-port wiring rule, fan-out recipients and the embargo pause, ingress
  never writing the ledger, the held out-of-order Announce, arrival-order
  independence (SYNC-19), divergence recovery,
  the sender's ledger position on every case activity, replay rate limiting, and
  SYNC test patterns.
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
  CASE_MANAGER's check of its own copy on a hash-mismatch fault, and the send-side
  check all call `ledger_entry_hash_intact()`. A second copy of the hashing logic
  can disagree with the first and blame the wrong side (SYNC-03-010, #5095).
- **The CASE_MANAGER holds back an entry it cannot verify** (SYNC-03-009). Every
  `send_announce_log_entry` call (fan-out, `Reject` replay, embargo backfill,
  join-time backfill, and `Read` position-statement replay) goes through one core
  helper that checks first, so no send path can skip it. The helper sits at the port
  call, below `send_ledger_suffix`, because the fan-out of a new entry bypasses that
  loop. A replay stops at the broken entry: a replica
  can only hold what follows as a forward gap. Fan-out checks the entry it built in
  memory, unless it reused a recorded one or backfills a paused peer, so a storage
  round-trip bug usually surfaces at replay, which reads the stored copy.
- **A held-back send fails its node, except a fan-out's catch-up.** The node
  that holds back an entry returns `FAILURE` (BT-14-001), and inside an act's
  transaction the act then keeps nothing (CLP-07-015). So a broken *new* entry
  refuses its commit, and an Accept whose join backfill reaches a broken entry
  cannot commit. The `Reject` and `Read` replays commit nothing, so the entries
  queued before the broken one stay queued. The one exception is the fan-out's
  catch-up of a let-back-in, paused peer: that peer keeps its pause and is skipped
  for the new entry, every other recipient gets it, and the fan-out succeeds.
  Failing there would refuse every later commit in the case, since the peer's
  pause brings the same catch-up back each time (decided on #5120).
- **A hash refusal is reported, not recovered.** The replica sends
  `LedgerEntryRefused/HashMismatch`; the CASE_MANAGER logs it at ERROR and checks its
  own copy, and does nothing else. Replay and re-seed resend the same content, so
  neither can repair it; the replay cooldown bounds the loop (SYNC-03-007/008/010).

## Canonical Serialization

The hashed form must be fixed **before** entries are signed; changing it later
invalidates every chain. It needs deterministic key order, one stable Unicode
normalization, an explicit field set (signatures and cache fields excluded), and
no optional whitespace. [RFC 8785 (JCS)](https://www.rfc-editor.org/rfc/rfc8785)
is the target; the gap between it and the current serializer is #3659. Leaf
hashes must stay valid if the chain later becomes a Merkle tree (SYNC-01-005).

## Every Case Activity States Its Sender's Ledger Position (SYNC-18)

- **One slot, `ledgerPosition`.** Every case activity carries its sender's tail as
  the activity's `ledgerPosition`, the term and shape SYNC-16-005 puts on a case
  copy, so one fact keeps one wire form (ADR-0156). Add no position to `content` or
  `context`: the full-case Invite, its replies and `Reject(CaseLedgerEntry)` use
  `ledgerPosition` too (VAM-04-011..014, SYNC-16-007).
- **Stamp in the factory, from the sender's store.** The adapter that builds the
  activity reads the tail with `ledger_tail_position()` and has
  `stamp_ledger_position()` put it on (`with_sender_ledger_position`), before the
  activity is stored or sealed, so the stored activity, the sealed body and the
  CASE_MANAGER's own entry agree. A resend relays the sealed body, so it keeps the
  first position (SYNC-18-002, OX-07-001).
- **Scope is decided by the receiver's event class.** A `LedgerPositionedEvent`
  requires the position at the parse edge (SYNC-18-003); every other received
  semantic is listed with its reason in `test/wire/as2/test_ledger_position_scope.py`.
  The sender stamps whenever its store holds the case's ledger, so an activity sent
  before that is never stamped. `Read(CaseLedgerEntry)` is in scope: the entry it
  names is the sender's tail. `Create(ProcessingFault)` is out: any receiver sends
  one, even for a body it could not parse, and it names no case (ASK-07-001).
  `Reject(CaseLedgerEntry)` admits no position, from a peer that holds no case yet.
- **A lag is a record, never a refusal.** Log it at DEBUG and judge the act as
  before (SYNC-18-004). An answer to a replaced embargo is already caught, because
  its consent row accepts no trigger (CM-18-003); CM-11-012's floor is the one
  per-activity rule.
- **A split is a repair.** A position the CASE_MANAGER does not hold means the
  sender's chain split from the canonical ledger: log at ERROR and re-seed an
  active participant through SYNC-16-003's rate-bounded path (SYNC-18-005).
- **The stamp is a position statement.** It says the sender has applied up to
  that entry, the fact `Read(CaseLedgerEntry)` states in a quiet period. Answer it
  the same way: record the acknowledged position and replay a lag, for active
  participants only (SYNC-18-007, composing SYNC-17-003/004).

### Open Questions

- **How the CASE_MANAGER answers a split position.** SYNC-18-005 admits the act
  and re-seeds the sender. Two alternatives stay open: log only, waiting for the
  participant's own divergence fault (SYNC-16-001), or refuse the act, as
  CM-11-012 refuses a full-case reply naming an entry the ledger lacks. Refusing
  makes the stamp a gate after all; revisit when a split is seen outside a test.
  The `Read` answer to a split differs today (SYNC-17-005: WARNING, nothing sent);
  decide both together.

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

## No Decision Depends on Arrival Order (SYNC-19)

The ledger's `log_index` is the one order the protocol defines, and eventual
consistency is its guarantee (ADR-0161). Every other arrival order is noise, so a
decision that reads it is a bug against SYNC-19-001. The maintained list of direct
messages and their verdicts is the table in
`docs/topics/case_lifecycle/case_ledger_sync.md` § "Messages the CASE_MANAGER sends
outside the ledger".

- **The CASE_MANAGER's observation order is the order.** Taking concurrent
  assertions from different senders as they arrive is correct: the ledger records
  that order, and the later one is refused with a notice the ledger explains.
  Reason: CLP-14-001 makes that order the case's causal order.
- **Never count on per-recipient order.** Our outbox delivers in order per
  recipient (OX-01-005), which hides reordering in end-to-end runs; a lost
  `Announce` replayed later breaks it. Test a race by delivering the messages in
  every order through `LedgerNetwork.receive`, never through the outbox
  (SYNC-19-003).
- **A direct message is stored, not applied.** A message the CASE_MANAGER sends
  outside the ledger stores a record or closes a pending assertion; the replica
  takes its effect from the ledger entry (RSH-08-003). Reason: a message that
  writes case state races the entry that writes it too. The ending notices to a
  paused signatory are the exception, and diverge when reversed (#5201).
- **A replica's answer must not turn on its related entry.** A relayed message can
  arrive before or after the entry it relates to, so a guard reading the state that
  entry changes answers twice differently. The owner's auto-accept reads EM `NONE`,
  which the proposal's own `PROPOSE` step changes (#5199).
- **A replica-local index must end where the ledger puts it.**
  `pending_embargo_proposal_index` is written by relayed Invites, by ledger apply and
  by case copies, so the last writer wins; a late Invite leaves a decided proposal
  open (#5200). Write such an index idempotently and prune it against the register,
  whichever writer arrives last.
- **One sender's back-to-back assertions are unordered.** The CASE_MANAGER cannot
  see send order, and both assertions carry the same `ledgerPosition`. Two that
  conflict are recorded in arrival order: an Accept and a Reject of one Invite
  (#5202), or an assertion and the sender's own Leave (#5203).
- **Expect the relayed Invite before its emission entry.** The CASE_MANAGER commits
  each emission after queueing it (SYNC-09-002), so the steady state delivers the
  Invite first; the replica arm must not need its emission entry.
- **Every new direct message gets a verdict.** Classify it by the rules above, add a
  row to the docs table, and add it to
  `test/core/use_cases/received/test_arrival_order.py` if it can race its ledger
  entries ([`vultron/core/AGENTS.md`](../vultron/core/AGENTS.md) § "Adding a New
  Message Type").

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
- **Find the case through the refused `Announce`.** The fault carries no case
  (ASK-07-006); its `inReplyTo` names the `Announce(CaseLedgerEntry)` the
  CASE_MANAGER stored when it sent it, so `announced_ledger_entry()` reads the
  entry, and with it the case and index, from there (SYNC-16-003).
- **One response per failure class.** `CreateProcessingFaultReceivedUseCase`
  maps each class with an effect to a `FaultResponse` (tree builder and verdict
  reader) in `responses`; a new class adds an entry, never a branch in
  `execute()`, which runs one tree whatever the class (CLP-10-005). Every acting
  class shares the one declared sender rule (HP-01-007).
- **Re-seed a replica only through `ReseedPeerNode`.** It holds the CM-10-004
  gate, the per-peer cooldown and the record of the copy's position, so any other
  trigger for a fresh copy to a replica that holds the case (SYNC-18-005) composes
  it (SYNC-16-004). The genesis pre-seed is a first seed bounded by the replay
  guard instead (SYNC-15-014); both build the copy with `announce_case_to_peer()`.
- **A case stores the ledger position it is a projection of.** Only
  `store_ledger_entry()` moves it, in the transaction that stores the entry, on
  every commit and replica store. A node that saves or snapshots a case it read
  before committing passes it through `at_stored_position()` first, or the save
  puts the position back and the snapshot names a stale one (SYNC-16-005).
- **A position never moves back.** Storing an entry at or before the case's
  position leaves the position where it is: a replica seeded ahead of its chain
  stores the replayed entries as no-ops, and moving back would make the next
  copy look ahead again (SYNC-16-007).
- **A different entry at the position is refused, never stored.** The entries
  before the position carry no hash the case names, so a divergence among them
  shows only at the position's index. `CheckEntryAgreesWithCasePositionNode`
  refuses that entry at ERROR before any effect, and `store_ledger_entry()`
  raises for it, so the chain never names one entry and the case another
  (SYNC-16-007).
- **A case copy is judged by the position it names.** Chain already past it:
  stale, `SKIPPED`, because an old copy can arrive late. A different entry at its
  index: `REFUSED` at ERROR. Otherwise the copy replaces the case, position
  included (SYNC-16-006). A repeat of an earlier Announce takes the same
  judgement, so it replaces the case only while it is still current
  (`services/case_copy.py`).
- **A copy carries each record as the store holds it now.** `_case_for_wire`
  re-reads a participant or report the case holds inline, because a current
  copy replaces the replica's participant records unconditionally; a stale
  inline snapshot regressed a replica's RM (#4797). The CASE_MANAGER skips a
  copy of its own, as it receives its broadcast as a participant: its case is
  the source.
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
  CASE_MANAGER reads the case through the event's `replay_case_id`, never the entry.
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

## A Participant Checks with Read(CaseLedgerEntry) (SYNC-17, ADR-0155)

The CASE_MANAGER learns how far a participant has got only from the participant.
Reason: the gap `Reject` fires only when a later entry arrives, so a lost last entry
before a quiet period leaves the replica behind with no signal on either side.

- **`Read`, never `Reject`, for a check** (SYNC-17-001). `Read` states a fact; a
  `Reject` of an entry nothing refused would mislead other implementations.
- **One answer**: record the position, replay if behind (SYNC-17-003/004). The
  position stated on every case activity (#5109, #5110) composes this answer, never
  a copy of it.
- **No CASE_MANAGER sweep.** `last_acknowledged_hash` is written only by a stated
  position or a `Reject`, so comparing it with the tail on a timer or on commit
  reads every quiet peer as behind; and a paused peer lags on purpose.
- **Active senders only** (SYNC-17-002): a removed, unconsented or closed peer's
  `Read` is `REFUSED` and answered with nothing; its catch-up is CM-10-006's backfill.
- **Same replay guard.** A `Read` replay goes through `should_replay()` /
  `record_replay()` and the outbox de-duplication, like a `Reject` replay. A `Read`
  can predate entries already in flight, so only the rate bound limits the
  redundant replays.
- **Never ledgered** (SYNC-17-006): a `Read` is an observation (ADR-0152).
- **A fresh id per statement**, unlike a rebuildable send (SYNC-09-002): a repeat
  is a new observation the CASE_MANAGER must answer, and a derived id would be
  skipped as a redelivery (`SyncActivityAdapter.send_read_ledger_entry`).
- **The restart round waits for the startup inbox replay** (IE-06-006), so the
  stated tail includes every entry the queue held; a shutdown during that wait
  states nothing (`ledger_position_statements.py`).

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
