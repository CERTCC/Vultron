---
title: Inbox Orchestration — BT Module Design
status: active
kind: guidance
description: >
  Rules for the core BT-backed inbox orchestration module: orchestration
  belongs in core/, the narrow route-level guard exception, the two-adapter
  seam and verdict mapping, the path from receipt to permanent storage (ingress
  writes nothing; one staged record per message holds a deferred activity),
  redelivery detection and the reused-id refusal, which evidence a routed copy
  carries, the door order and the seen-before door's answer to a resend, what
  each final outcome leaves (the archive, a receipt stub, the hold),
  when the per-case expiry window restarts,
  the internal-error fault for a raised dispatch,
  the queue replay's bounded retry and held fault, what is left of the
  staged-record migration (ADR-0153, ADR-0154), the
  sender-sequence hold that returns a record to HELD (ADR-0178),
  pending-queue port injection, and the test surface.
related_specs:
  - specs/sync-ledger-replication.yaml
  - specs/inbox-orchestration.yaml
  - specs/case-ledger-processing.yaml
  - specs/participant-case-replica.yaml
  - specs/use-case-organization.yaml
  - specs/handler-protocol.yaml
  - specs/inbox-endpoint.yaml
  - specs/datalayer.yaml
  - specs/idempotency.yaml
  - specs/protocol-asks.yaml
  - specs/actor-knowledge-model.yaml
related_notes:
  - notes/architecture-hexagonal.md
  - notes/use-case-protocol.md
  - notes/bt-integration.md
  - notes/architecture-adapters.md
  - notes/case-communication-model.md
  - notes/inbox-pipeline.md
relevant_packages:
  - vultron/core/behaviors/inbox
  - vultron/adapters/driving/fastapi
---

# Inbox Orchestration — BT Module Design

## Orchestration Belongs in `core/`

A change to inbox processing (parse, rehydrate, defer-check, dereference-check,
dispatch) belongs in
`vultron/core/behaviors/inbox/` (IO-02-001), never in the FastAPI router or a new
adapter-layer pipeline helper. `process_payload` is the sole caller-facing entry point
(IO-02-003) and all policy is internal to the BT. Logic in the router is unavailable to
non-HTTP entry points (CLI, tests) and violates ADR-0009.

The FastAPI inbox endpoint is thin glue: parse the body, return 202, and schedule
`process_payload` through `BackgroundTasks`. The scheduled task is a coroutine, so it
runs `process_payload` and the pending-queue replay through `asyncio.to_thread`; a
synchronous BT tick on the event loop stalls every other request, delivery, and outbox
drain on the container (IE-06-003). See [bt-integration](bt-integration.md) §
"Concurrency Model".

---

## Exception: Synchronous Route-Level Guards

IO-03-003b forbids inbox policy in the FastAPI path, with one narrow exception
(IO-03-007): a **synchronous guard that refuses an activity before the 202** may live
at the route, because the sender needs a 4xx and the check must run before
`BackgroundTasks` schedules the handler. The addressing check (IE-11-001, ADR-0068)
is the example. A route-level guard:

- produces a synchronous HTTP response, not a flag for a downstream node;
- does not duplicate orchestration logic that belongs in the core BT;
- is justified in an ADR that acknowledges IO-03-003b.

---

## Two-Adapter Seam

`process_payload` takes exactly two adapters (`vultron/core/behaviors/inbox/models.py`):
`IngressPayloadAdapter` owns parse and rehydrate, keeping wire knowledge out of the BT;
`DispatchAdapter` runs the use-case path and returns its `HandlerResult` (IO-03-005).
Collapsing them re-couples parsing to dispatch; splitting further lets callers invoke
the steps out of order.

`DispatchNode` is the only place a verdict becomes an outcome (HP-01-004):
`APPLIED`/`SKIPPED` → `processed`, `DEFERRED` → `deferred`, `REFUSED` → `rejected` with
the handler's reason. A dispatch that returns no `HandlerResult` is rejected ("did not
raise" is not a verdict), and semantics with no use case get a `REFUSED` "no use
case found" verdict from the dispatcher, so they are rejected too (UCORG-05-012).
`run_inbox_pipeline` logs every `rejected` outcome at WARNING with actor and activity
ids (UCORG-05-013); the BT nodes log their own outcome writes at INFO, so a refusal is
not reported twice.

Every deferral gate asks `is_deferral_exempt()` (`core/models/events/case_context.py`),
never `is_case_bootstrap()`: a stub Invite is exempt because it precedes its case by
design, but it seeds no case, so only a bootstrap triggers the replay (PCR-06-005, #4915).

Activities held pending a case bootstrap are replayed only when the bootstrap's verdict
maps to `processed` (the legacy adapter paths gate on `HandlerResult.took_effect`): a
refused or deferred bootstrap has not made the case available, so replay would only
defer them again. A replay that raises is logged and does not turn an applied bootstrap
into `rejected` (MV-01-007).

---

## From Receipt to Permanent Storage

An inbound activity reaches the receiver's permanent store in three steps, and only
the last one writes what it carries:

1. **Ingress writes nothing** (DL-06-006, CLP-10-038). Not the activity: a row under
   the id its sender chose is read as one of the receiver's own by every "did I send
   it" scan (`case_is_announced`, `recorded_stub_invites`, #4866). Not its inline
   objects: a stored inline object *is* the receiver's record, so a stored case is a
   replica whose trust check trusts the sender's own snapshot (PCR-03-004, #4674).
2. **Routing reads through a staging store.** The routed activity is rebuilt by the
   store's read pipeline, which is what turns the parsed graph into the shape the
   patterns match, so the activity's row and its inline objects are staged in
   `InlineObjectStaging` (`vultron/adapters/inbox_staging/staging.py`): an
   in-memory store read after the receiver's own store for every other id, and
   emptied around each use. Without the staged object the activity's `object_`
   stays a bare id, which no pattern's object type accepts (SE-01-006), so an
   activity whose sender carried its object inline would be read as
   `UNKNOWN_UNRESOLVABLE_OBJECT`.
3. **The handler writes the core record, after its guards** (CLP-10-039). Once the
   door guards admit the message, intake records the received body as a `HELD`
   `ReceivedActivityRecord` under the receiver's key (CLP-10-010, CLP-10-017), and an
   effect node writes any record from the copy the event carries (the add-note tree's
   `StoreReceivedObjectNode`, `SeedCaseReplicaNode`). A door's refusal writes nothing,
   and a guard's nothing past that record, so nothing is left to remove.
4. **The outcome stage decides what is kept** (CLP-10-073). It is a decorator on
   `DispatchNode`, so it runs on every path the dispatch can take and returns the
   dispatch's status unchanged: applied or skipped moves the record to `ARCHIVED` with
   its sealed body; refused gives the body up for a receipt stub, written from the
   delivery's own body when a door refused before intake; deferred leaves the holding
   record. It is a decorator and not a sibling because the inbox pipeline is a
   `Sequence`, whose later children do not run once a refusal fails the dispatch.

A reader that needs a received activity later loads its body: core through
`read_received_activity` (a read-only view), a reply through
`vultron/adapters/received_archive.py`; never under the sender's id. A reader *inside*
the run that embeds the body of the message being handled — the refusal notice — reads
it through `held_received_body`, from the holding record, whatever body-bearing stage
it is in (CLP-10-073). None of them finds a body on a receipt stub.

**A refusal keeps the receipt, not the message** (CLP-10-018). What is left of a
refused delivery is a `REFUSED`-stage record with no body: the sender, the sender's
activity id, the time of receipt the record already carried, the reason, and the
digest of the body (`received_body_digest`, the one definition both this and the
reused-id check at ingress use). Write it only through
`vultron/core/services/received_outcome.py`. Two things it refuses: a delivery whose
body is still owed to a replay, because that replay would route a body the stub had
dropped; and a second refusal, which leaves the first reason standing.

**No verdict is not an outcome** (CLP-10-074). A dispatch that raised and one that
returned no `HandlerResult` leave the record exactly as it is, `HELD` with its body:
the act rolled back keeping nothing (ADR-0151), so the resend or re-run must be able to
run it again from that body. The outcome stage tells them apart by the disposition
`DispatchNode` publishes, which is written only when a verdict came back. A semantic
type no use case handles is not one of them: it is `REFUSED`, so it leaves a stub,
because a body kept for it would let any sender make the receiver store whatever it
liked by choosing a type the receiver does not handle (ADR-0154).

**The doors run before anything is written, in ADR-0154's order** (CLP-10-010):
addressed to me, seen before, which path, open to writes and the sender entitled
(the post-close boundary beside the closed-sender door and the sender guard), then
intake, then the handling tree. A message a door turns away costs one read and a
receipt stub. Never place a writer, or a reader of what intake wrote, ahead of the
last door.

**A resend is answered from its record, never re-run** (ADR-0154). The seen-before
door (`case/nodes/seen_before.py`) reads the one record and its stage only: a stub is
`REFUSED` again with its reason, an archive is `SKIPPED`, a record owed a replay is
`SKIPPED`, and nothing after the door runs, so no refusal notice goes out again. A
`HELD` record owing nothing lets the delivery through: inbox runs are serialized per
actor, so a resend never meets a run in progress, only a run that ended with no
verdict, which must run again. A nested received tree (the close-case tree's inner
one) meets its enclosing tree's record the same way and passes. The door compares no
bodies: ingress does that once, so a reused id never reaches it (IE-10-002). Handlers
read its answer through `door_refusal`, which may now return `SKIPPED`.

**One message, one record** (ADR-0154). An activity the inbox defers is held on its
own `ReceivedActivityRecord`, the same row intake records to, under the key the
receiver derives. `DeferredInboxActivity` and the `VultronPendingCaseInbox` activity
list are retired into it. The record carries two facts, and both values of the flag
are reachable in holding, so neither can be read off the other:

- `stage` — `HELD` for a message in holding (waiting, being handled, or left by a run
  with no verdict), `ARCHIVED` once the outcome stage archived an applied message
  (CLP-10-073), `REFUSED` for a receipt stub, which keeps no body at all
  (CLP-10-018);
- `replay_owed` — whether a replay is still owed from the held body, because the
  delivery that carried it ended without routing it. It waits on its case
  (`awaiting_case_id`), on a ledger gap (SYNC-14-001), on an object fetch
  (AKM-05-007), on a retry, or, at the CASE_MANAGER, on a gap in its sender's
  `senderSequence` (SYNC-21-010).

**A sender-sequence hold turns the record back to `HELD`** (`hold_unjudged_for_replay`):
the activity has not been judged, so its replay is recorded afresh by intake and
judged as a first delivery, refusal notice included (CLP-02-005). A record still
owed a replay is `HELD`, never archived, so a resend meets the seen-before door's
"waiting" answer and the replay is the only run that judges it. What is due is read from the
`SenderSequenceOrder` record, never kept in a second list, and the inbox's
`dispatch` queues it after every dispatch (`queue_due_held_activities`).

An archive never owes a replay, and the record's validator refuses one: a replay of
an applied message would apply it twice. A buffered `Announce(CaseLedgerEntry)` is
the case that tempts it: intake recorded it and the handler then held it for its gap,
so it stays `HELD`, owing a replay, and the outcome stage does not archive it. Its
release hands the body to the replay, which records it again as a delivery of its own
(IO-03-009); its eviction drops it, body and all (SYNC-14-013). A message already at
its outcome is never held again. Go through
`vultron/core/services/received_holding.py` for every one of those transitions — it
is the one place the pairing is kept straight.

`replay_owed` is also what decides whether a routed copy carries received evidence,
which is why the decision reads the record and not a record type: a replay routes the
held body **with** its evidence, because the copy routed is the delivery held
(VM-08-008); a *new* delivery answered by a record that still owes a replay routes
the held copy **without** evidence, because that copy is not this delivery and will
carry the evidence when it is replayed (VM-08-010); and a new delivery answered by a
record owing nothing routes the held body **with** its evidence, because that body is
the first delivery's (VM-08-009).

**What waits for a case is read from the waiting messages**, each naming its case in
`awaiting_case_id`, in arrival order (`received_at`); `records_awaiting_case` is the
read. `VultronPendingCaseInbox` keeps only what is per case: the stub Invite's trust
anchor, and `queued_at`, the one clock that opens the CBT-03-001 window. Keeping that
clock per case preserves its restart when an anchor-only record takes its first
waiting message, so an invitee's thinking time is not charged to the queue.

**The record's optional fields are checked, not conventional.** `received_body` is
required in every stage but `REFUSED`, and `sender_id`, `refusal_reason` and
`body_hash` only in `REFUSED`, so four fields are `X | None` against ARCH-10-001's
fail-fast rule. A discriminated union or a separate stub class would have typed them,
but the seen-before door must be one read of one row, which a union makes two. The
price is paid by `_a_stub_keeps_no_body`, a `mode="after"` validator that refuses a
body-bearing stage with no body, a body-bearing record carrying any of the stub's
three, a stub that kept its body, a stub missing any of its three, and a stub that
owes a replay. Extend that validator rather than adding a second mechanism, and pin
any new pairing in both directions.

**Read "was anything already waiting?" before the hold, never after.** The hold is
what makes an activity one of the waiting, so a reading taken afterwards always
finds at least this activity and cannot tell a first arrival from a redelivery of
the only waiter — which is what decides whether `queued_at` restarts
(`_case_window_is_open`, CBT-03-001). Taking it after reopened the expiry window on
every redelivery, so a sender redelivering inside the window held the pre-bootstrap
queue open for ever, against CBT-03-003's bound. The retired `activity_ids` list hid
this by answering membership directly; a list replaced by a derived read loses that,
and any "is this the first one?" question over such a read has the same trap.

**Hold before you queue**: the record is the activity's only copy, so an id queued
with nothing held behind it is lost, and `hold_for_replay` raises rather than queue
one (DL-06-006).

**A redelivery is detected from the receiver's own key** (IE-10-001): a deferred
record routes the held copy, without received evidence, and keeps it for the
replay; a record owing nothing routes the held body's parse, carrying that body as
its evidence, because it is the first delivery's sealed body (VM-08-009, VM-08-010). The
tree's seen-before door then answers it from the record's stage (ADR-0154). Never
route the redelivered body.

**Compare the body before you route the held copy** (IE-10-002): only a resend
whose sealed body exactly matches the held one is a redelivery. A different body
under a held id is refused with a WARNING naming the activity id and sender, and
neither body is routed nor anything written; routing the held copy in its place
silently dropped the new body (#3762). The match is exact, with no normalisation,
so a body re-serialized with a different key order is refused too. The rule covers
every activity type: an `Announce(CaseLedgerEntry)` hydrated in place (SYNC-13-004)
gets the same comparison, and only a same-body repeat reaches SYNC-12-003's gate.
Both sides of the match are always sealed: a deferred record holds only the sealed
body (ADR-0149), and an unsealed activity can neither be deferred nor compared, so it
raises `VultronWiringError` (ARCH-15-001) rather than guess a match
(`test_ingress_received_evidence.py`).

**A failed act stays in holding, not in the archive.** A received act that failed kept
no entry and no verdict, so its record stays `HELD` and its redelivery runs again,
committing the held body; an applied act's redelivery is `SKIPPED` at the seen-before
door. `CommitCaseLedgerEntryNode` keeps the first entry when the ledger already
records the activity as the same semantic, which covers a tree whose own repeat
guard sits after the commit: RM engage guards only its CASE_MANAGER effects, so
the commit's equivalence check is what keeps that entry single (#5006). Add no
repair pass and no "redelivered, so skip" shortcut at ingress (ADR-0151,
`test_failed_act_redelivery.py`).

**A raised dispatch is answered with a fault** (ASK-07-010, ASK-07-011):
`DispatchNode` logs it once at ERROR with the activity and sender ids and queues
one internal-error `Create(ProcessingFault)` to the sender through `DispatchAdapter`.
A live delivery is never retried, so only the sender's own resend, which the fault
invites, can later succeed. A queued replay is retried (IE-06-004,
`inbox_queue_drain.py`), so its
`ReplayDispatchAdapter` holds the fault and sends it only when the item is
dead-lettered or dropped as a protocol violation, never on a re-queue, or a later
success would follow a false fault (ASK-07-007). A raise after the dispatch returned
(the post-bootstrap replay) is logged by `DispatchNode` and is neither retried nor
answered. Never answer a raised
`Create(ProcessingFault)` with a fault (`answers_with_internal_error_fault`), or two
peers failing alike answer each other forever. The fault goes to the claimed `actor`:
the inbox does not authenticate senders yet (#509). It is not ledgered (#4800).

**The queue replay retries back to back and settles on what it saw.** A re-queued item
goes to the back of the inbox queue and is attempted again in the same drain, so the
retries are not spaced in time; the persisted count matters across runs. The rebuild
releases the held record, so a rejection after the rebuild and before dispatch (a node
that caught its own raise, such as extraction) is retried like a raise, or the item is
lost; a handler's verdict is final. A dead-lettered item stays held for the operator, so
a resend of it routes the held copy as a redelivery (IE-10-001) and does not release it.

**What is left of the staged-record migration.** `Offer(VulnerabilityReport)` still
stores what it carried before its own late addressee check, under the
`OFFER_REPORT_STORED_FIRST` exemption, until it takes the no-case path (#5046); and
nothing yet finds a record a crashed run left in holding on restart, or proves every
handling tree safe to run twice from holding (#5047). New work should add no
receiver-role gate outside the path stage and no reader of in-memory state an earlier
stage left (ADR-0154).

---

## Pending-Queue Port Injection

The defer-check step reads and writes the pending-case queue through the injected
`PendingCaseQueuePort` (IO-03-002), never by importing `inbox_pending_queue` from the
adapter layer. The FastAPI adapter supplies the concrete implementation; tests supply an
in-memory stub. This keeps `core/` free of adapter imports (ADR-0009).

The dereference-check step does the same through `ObjectDereferencePort`
(`vultron/core/ports/object_dereference.py`): core decides what an activity must fetch
first (`references_to_fetch`, AKM-05-007), and the port holds the activity and records
the fetch. Never fetch inside the step or under the actor's inbox lock: a fetch can
wait out its retries, and the actor's deliveries must not wait with it (IE-06-002). The
adapter makes open fetches after the inbox run, on the event loop, and settles each
under the lock (`inbox_dereference.resolve_open_fetches`), so the replay goes through
the same drain as any queued item (IE-06-004).

---

## Test Surface

Tests target `process_payload` and observe `InboxOutcome.status`, `context_id`, and the
queue port's recorded calls. They MUST NOT monkeypatch internal BT node helpers.
