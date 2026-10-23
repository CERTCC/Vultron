---
title: Inbox Orchestration — BT Module Design
status: active
kind: guidance
description: >
  Rules for the core BT-backed inbox orchestration module: orchestration
  belongs in core/, the narrow route-level guard exception, the two-adapter
  seam and verdict mapping, the path from receipt to permanent storage (ingress
  writes nothing; a deferred activity is held whole), redelivery detection and
  the reused-id refusal, the internal-error fault for a raised dispatch,
  the queue replay's bounded retry and held fault, the planned staged-record
  and path-stage replacement of intake-first (ADR-0153, ADR-0154),
  pending-queue port injection, and the test surface.
related_specs:
  - specs/inbox-orchestration.yaml
  - specs/case-ledger-processing.yaml
  - specs/participant-case-replica.yaml
  - specs/use-case-organization.yaml
  - specs/handler-protocol.yaml
  - specs/inbox-endpoint.yaml
  - specs/datalayer.yaml
  - specs/idempotency.yaml
  - specs/protocol-asks.yaml
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

A change to inbox processing (parse, rehydrate, defer-check, dispatch) belongs in
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

IO-03-003b forbids inbox policy in the FastAPI path, with one narrow exception: a
**synchronous guard that refuses an activity before the 202** may live at the route,
because the sender needs a 4xx and the check must run before `BackgroundTasks`
schedules the handler. The addressing check (IE-11-001, ADR-0068) is the example. A
route-level guard:

- produces a synchronous HTTP response, not a flag for a downstream node;
- does not duplicate orchestration logic that belongs in the core BT;
- is justified in an ADR that acknowledges IO-03-003b.

---

## Two-Adapter Seam

`process_payload` takes exactly two adapters (`vultron/core/behaviors/inbox/models.py`):
`IngressPayloadAdapter` owns parse and rehydrate, keeping wire knowledge out of the BT;
`DispatchAdapter` runs the use-case path and returns its `HandlerResult` (IO-03-001).
Collapsing them re-couples parsing to dispatch; splitting further lets callers invoke
the steps out of order.

`DispatchNode` is the only place a verdict becomes an outcome (HP-01-004):
`APPLIED`/`SKIPPED` → `processed`, `DEFERRED` → `deferred`, `REFUSED` → `rejected` with
the handler's reason. A dispatch that returns no `HandlerResult` is rejected ("did not
raise" is not a verdict), and semantics with no use case raise in the dispatcher, so
they are rejected too (UCORG-05-012). `run_inbox_pipeline` logs every `rejected`
outcome at WARNING with actor and activity ids (UCORG-05-013); the BT nodes log their
own outcome writes at INFO, so a refusal is not reported twice.

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

1. **Ingress writes nothing** (DL-06-006, CLP-10-017). Not the activity: a row under
   the id its sender chose is read as one of the receiver's own by every "did I send
   it" scan (`case_is_announced`, `recorded_stub_invites`, #4866). Not its inline
   objects: a stored inline object *is* the receiver's record, so a stored case is a
   replica whose trust check trusts the sender's own snapshot (PCR-03-004, #4674).
2. **Routing reads through a staging store.** The routed activity is rebuilt by the
   store's read pipeline, which is what turns the parsed graph into the shape the
   patterns match, so the activity's row and its inline objects are staged in
   `InlineObjectStaging` (`vultron/adapters/inbox_staging.py`): an
   in-memory store read after the receiver's own store for every other id, and
   emptied around each use. Without the staged object the bare id mis-routes,
   because permissive patterns accept a string `object_`: `Create(id)` routes as a
   report.
3. **The handler writes the core record, after its guards** (CLP-10-019). Intake
   archives the received body as a `ReceivedActivityRecord` under the receiver's key, and
   an effect node writes any record from the copy the event carries (the add-note
   tree's `StoreReceivedObjectNode`, `SeedCaseReplicaNode`). A refusal writes nothing
   past the archive, so nothing is left to remove.

A reader that needs a received activity later loads its body: core through
`read_received_activity` (a read-only view), a reply through
`vultron/adapters/received_archive.py`; never under the sender's id. An activity
deferred until its case is known is held whole in one `DeferredInboxActivity`
(IO-03-004): the sealed received body and its staged inline rows, nothing derived
from them (ADR-0149). Its replay parses the body again, so it carries the first
delivery's evidence (VM-08-002); the replay, or the queue's expiry, deletes the
record. A held out-of-order `Announce(CaseLedgerEntry)` (SYNC-14-001) is held the
same way, as the body that arrived, and its replay (SYNC-14-009) deletes the record.
**Hold before you queue**:
the record is the activity's only copy, so an id queued with nothing held behind it
is lost, and `hold_for_replay` raises rather than queue one (DL-06-006).

**A redelivery is detected from the receiver's own key** (IE-10-001): a deferred
record routes the held copy, without received evidence, and keeps it for the
replay; an intake archive routes the archived body's parse, carrying that body as
its evidence, because it is the first delivery's sealed body (VM-08-002). The
handler's idempotency answers it (ID-02-003). Never route the redelivered body.

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

**The archive records receipt, not the act.** A received act that failed kept no
entry, so the idempotency guards do not see it and its redelivery runs as a first
delivery, committing the archived body; a committed act's redelivery is still
`SKIPPED`. `CommitCaseLedgerEntryNode` keeps the first entry when the ledger already
records the activity as the same semantic, which covers a tree with no repeat guard
of its own (RM engage). Add no repair pass and no "redelivered, so skip" shortcut at
ingress (ADR-0151, `test_failed_act_redelivery.py`).

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

**The intake-first order above is being replaced; don't build on it.** Two proposed
records reorder a received message's questions so an early answer ends the run before
anything is stored: one role check per message picks the received path (ADR-0153),
and each message becomes one staged record, archived only when applied, with a refused
one leaving a receipt stub (ADR-0154). Until #5041–#5047 land, the steps above still
describe the code, but new work should not add another receiver-role gate or another
reader of intake's archive of a refused message: both are what the migration removes.

---

## Pending-Queue Port Injection

The defer-check step reads and writes the pending-case queue through the injected
`PendingCaseQueuePort` (IO-03-002), never by importing `inbox_pending_queue` from the
adapter layer. The FastAPI adapter supplies the concrete implementation; tests supply an
in-memory stub. This keeps `core/` free of adapter imports (ADR-0009).

---

## Test Surface

Tests target `process_payload` and observe `InboxOutcome.status`, `context_id`, and the
queue port's recorded calls. They MUST NOT monkeypatch internal BT node helpers.
