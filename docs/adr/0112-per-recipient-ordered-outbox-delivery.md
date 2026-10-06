---
status: accepted
date: 2026-09-29
created: 2026-09-29
updated: 2026-09-29
revision: 1
deciders: Allen D. Householder
consulted: >-
  notes/outbox-delivery-reliability.md, notes/sync-ledger-replication.md,
  specs/outbox.yaml, specs/sync-ledger-replication.yaml,
  docs/adr/0066-outbox-terminal-state.md,
  docs/adr/0037-buffer-out-of-order-ledger-entries.md,
  docs/adr/0059-buffer-pre-genesis-ledger-entries.md,
  issues #3602, #3878, #3033, #2898
informed: CERT/CC Vultron protocol team
stakeholder_type: [project-contributor]
---

# Per-Recipient Ordered Outbox Delivery: One Drain per Actor, One In-Flight Row per Recipient

## Context and Problem Statement

An actor's outbox is one persistent FIFO of activity ids (OX-01-002).
The CASE_MANAGER replicates its ledger by appending one `Announce(CaseLedgerEntry)` row per participant for every entry it commits (SYNC-02-003), so a fan-out of entry *N* to three participants is three consecutive rows, and the fan-out of entry *N+1* follows behind them.

The queue is drained by `outbox_handler`, and `outbox_handler` is called from three places: the background task that runs after every inbound activity, the legacy inbox handler, and the `OutboxMonitor`'s wake-on-enqueue loop.
Nothing serialised those calls.
Each concurrent drain popped the next row and awaited its HTTP POST, so the order in which rows *completed* delivery had no relation to the order they were enqueued.
In the `fvcv-handoff` run that motivated this decision (CI run 35917721682), the CASE_MANAGER's outbox had 28 deliveries in flight at once, and a 14-row backfill popped in order 0…13 reached the Coordinator as 4, 7, 1, 8, 5, 2, 10, 6, 11, 13, 12, 9, 3.

The receiver handles that correctly: it buffers every forward gap (ADR-0037) and sends a `Reject(CaseLedgerEntry)` per gap so a genuinely lost predecessor is replayed (SYNC-14-002).
The CASE_MANAGER handles each `Reject` correctly too: a `Reject` at an advanced position always replays the suffix (SYNC-15-010).
Together, under reordering the sender itself produced, they form an amplifier.
Ten `Reject`s from the Coordinator arrived after its gaps had already drained, each at a different advanced position, and each triggered a full-suffix replay — 116 duplicate `Announce` rows for entries the Coordinator already held, queued in the same FIFO as, and ahead of, the fan-out of entry 15 to every other participant.
The `Announce` of entry 15 to Vendor1 was enqueued at 20:46:22.0 and popped at 20:46:36.4; it waited 14.4 s in the queue behind rows for a different peer, and the scenario gate expired 0.25 s before it was applied.

The same amplifier is visible in the `fv` (#3033) and `fcvcv` (#2898) failures.
PR #3883 removed the two emission-order faults that *triggered* it there (a ledger fan-out queued before the `Create(VulnerabilityCase)` that seeds the case) and moved the inbound BT off the event loop.
It did not touch the drain, so any reordering — from concurrent drains, or from the re-queue-at-tail retry path (#3878) — still starts the loop.

Two questions are decided here:

1. What ordering does the outbox guarantee at delivery, and how?
2. Where does a failed row go when it is re-queued?

## Decision Drivers

- **The ledger transport needs order per recipient, not order across recipients.** A replica's hash chain is its own; whether the Finder receives entry 3 before the Coordinator does is irrelevant.
- **One slow recipient must not hold up the others.** A single serial drain restores order but reintroduces head-of-line blocking across peers, and a 30 s POST timeout (SYNC-05-004) to one unreachable peer would stall every other peer's rows.
- **Recovery must not be the normal path.** `Reject`/replay (SYNC-14, SYNC-15) exists for entries that are *lost*; a sender that reorders its own fan-out makes every recipient recover from a loss that never happened, and the replays land in the same queue.
- **No new persistence primitives.** The queue offers append, list, and pop (DL port); the fix must not need a new one, and whatever it holds outside the queue while delivering must go back to the queue on any interruption (ADR-0066's crash-safety stance, applied to a batch rather than a row).
- **Gates observe, they do not fix.** A demo gate that waits longer hides the queueing; a gate that names the late hop makes it visible (EDF-06, ADR-0058).

## Considered Options

### Option A — One serial drain per actor

Serialise `outbox_handler` per actor and deliver rows one at a time.
Restores OX-01-002 at delivery for every recipient, with the fewest moving parts.
Rejected on its own: one recipient's 30 s timeout blocks every other recipient's rows, which is the head-of-line hazard #3878 already names.

### Option B — Per-scenario drains and wider gates

Keep the transport as it is and have each scenario wait for ledger coverage before its next step (`wait_for_contiguous_ledger_coverage`), as #2819 did.
Rejected: it moves the transport's ordering obligation into every demo script, a scenario that omits the drain is still exposed, and it papers over a protocol-layer fault that a production deployment would also have.

### Option C — Re-queue a failed row at the head

Fixes #3878 alone: a failed row keeps its place.
The persistent queue has no head insert, and this does nothing about concurrent drains, which produced the reordering actually measured.

### Option D — One drain per actor, per-recipient lanes, lane-ordered re-queue, replay dedup (chosen)

Serialise drains per actor (Option A's lock) but schedule the rows of one drain in *lanes*: every recipient a row is addressed to is a lane, a row runs only when none of its lanes has a row in flight or waiting ahead of it, and distinct lanes proceed concurrently.
A row that fails past the per-pass cap stalls its lanes; nothing behind it in those lanes is attempted that pass, and the stalled rows are re-queued in their enqueue order.
Independently, a replay skips any (entry, peer) pair whose `Announce` is already pending in the outbox.

## Decision Outcome

Chosen option: **Option D**.

### One drain per actor outbox (OX-01-004)

`outbox_handler` takes a per-actor drain slot before draining (`vultron/adapters/driving/fastapi/outbox_handler.py`).
A caller that finds the slot held does **not** wait: it marks the slot "look once more" and returns, and the running drain re-reads the queue before it finishes, so nothing appended in the gap between that drain's last look and its release is left for the safety-net poll.
Waiting was rejected because it has a deadlock class: under Starlette's `TestClient` a recipient's `BackgroundTask` runs inside the sender's POST, so a loopback or round-trip delivery re-enters `outbox_handler` for the same actor while the outer drain is awaiting that very POST — the multi-app handoff test hung on the first version of this change.
Production uvicorn answers 202 before the task runs and never nests, but a drain policy must not have a deadlock class at all.
The slot registry is keyed by event loop, like the inbox's `_actor_inbox_locks`, because an `asyncio.Lock` binds to the loop it first waits on.

### Per-recipient lanes (OX-01-005, OX-01-006)

A drain pops the queue in batches — the queue as it stood when the pass looked — and hands each batch to `deliver_batch` in `vultron/adapters/driving/fastapi/outbox_lanes.py`.
A row's lanes are its recipients, resolved from the stored activity before delivery.
The drain slot is keyed on the store's canonical actor id, not the id the caller spelled — a trigger route forwards the URL segment while the inbox path passes the canonical URI, and both name one outbox.
A row whose activity cannot be read, or that names no recipient, gets a lane of its own: there is no recipient order to preserve, and `handle_outbox_item` reports it when it runs.
The scheduler starts every row whose lanes are all free, in pop order; a row blocked by a busy or earlier-waiting lane also blocks its lanes for the rows behind it, so order is preserved transitively; a row addressed to several recipients occupies every one of those lanes, joining them.
Rows appended while a batch is in flight form the next batch, after the current one completes, so a producer cannot slip a row ahead of one already in flight to the same recipient.

### Lane-ordered re-queue of a stalled row (OX-13-011, OX-13-012)

The in-pass retry ladder is unchanged: each failure increments the persisted attempt count (OX-13-001), exhaustion dead-letters the row and releases its lanes (OX-13-009), and a fourth in-pass failure stalls the row (OX-13-006, OX-13-011).
What changes is what "stalled" means for the rows behind it.
The stalled row's lanes carry nothing further this pass; every later row in those lanes is held back unattempted; and at the end of the batch the held rows are appended back to the queue in *stall order* — the order they were first held, which is their enqueue order.
The drain records that order for the whole pass, so a row appended by a producer during the pass, popped in a later batch and found to be in a stalled lane, is placed behind the rows that were stalled before it.
The pass ends when the queue holds only stalled rows, and the queue it leaves is in each lane's enqueue order for the next drain.

This satisfies #3878 without a head insert: the persistent FIFO still only appends at the tail, and the drain re-appends in the order the lane needs.

### Replay does not re-queue a pending Announce (SYNC-15-012)

`SyncActivityAdapter.send_announce_log_entry` reads the CASE_MANAGER's own outbox before queueing and declines a row whose `Announce` of that entry to that peer is already pending, reporting `False`; `SendMissingEntriesNode` counts only queued rows as sent (`vultron/adapters/driven/sync_activity_adapter.py`).
The outbox read lives in the adapter, not the node, because core must not read persisted activities back for their content (DL-06-001); the adapter that queued the row may inspect its envelope (DL-06-004).
SYNC-15-010 stands: a `Reject` at an advanced position still replays; it just cannot queue the same row twice.
A replay that finds everything pending sends nothing and records no position (SYNC-15-011).
With Option D's lanes in place this is defence in depth — the reordering that produced the stale `Reject`s no longer happens on the normal path — but a `Reject` that is itself delayed in the peer's outbox can still arrive after the gap has drained, and this bounds what it costs.

### An in-memory store's one connection is serialised across threads

Lanes deliver to distinct recipients concurrently, so in a single-process test (every actor on one `TestClient` app) the CaseActor's inbox worker thread and its outbox drain on the event loop touch the CaseActor's store at the same time.
An in-memory SQLite store uses `StaticPool` — every `Session` gets the *same* DB-API connection — and `check_same_thread=False`, and SQLAlchemy resets (rolls back) that connection when a `Session` returns it; so one thread's `Session.close()` discarded another thread's uncommitted insert.
Measured: a `Reject(CaseLedgerEntry)` the CaseActor had just stored was "not found" when the same pipeline re-read it, the Reject was dropped, no replay followed, and the peer's buffered entry never drained (2 of 4 `test_fv_demo.py` runs on the first version of this change; 0 of 4 on `main`, 0 of 6 after the guard).
`SqliteDataLayer._session()` now holds a per-engine re-entrant lock for the lifetime of every adapter `Session` when the engine's pool is `StaticPool` (`vultron/adapters/driven/datalayer_sqlite/engine.py` `session_guard`); file-backed engines use `NullPool` and get a no-op.
The lock wraps the `Session` block rather than the pool's checkout/checkin events because two concurrent fairies on `StaticPool`'s single record confuse the pool's own checkin bookkeeping — a checkin can go missing, and a lock keyed on it stays held.
This is not part of the outbox decision; it is the defect the outbox decision exposed, and it was already the shape the file-backed engine was hardened against in #659.

### The served process runs the safety-net drain, and a delegated emit drains the outbox it wrote to

The first CI run of this change failed at an *earlier* hop than #3602's: an ownership-transfer `Offer` sat unpopped in the CaseActor's outbox for 111 s (run 36643399281).
Two pre-existing faults met the new serialisation.
First, the trigger route drained the *requesting* actor's outbox, but a delegated emit (CM-24-001) is queued in the *CaseActor's*; `invite-actor-to-case` had fixed exactly this in #2484 and `offer-case-ownership-transfer` and `suggest-actor-to-case` had not.
Second, `main.py`'s root lifespan — the one uvicorn serves in every container — was a hand-written copy of `app_v2`'s that omitted the `OutboxMonitor`, and Starlette does not run a mounted sub-app's lifespan, so no container ever ran the OX-09-002 safety-net poll.
On `main` both were masked: with concurrent drains, some inline drain was almost always still looping when the Offer landed and picked it up within a second.
With one drain per actor, an activity queued in an outbox that nothing is draining waits for the next inbound activity to that actor.
The trigger routes now drain the outbox the trigger reports it wrote to (`_emitting_outbox`), and the root lifespan is `_make_lifespan(configure_globals=True)`, the same factory `app_v2` uses, so the two lists cannot drift again.
The TestClient-driven demo tests stop the monitor after startup: they assert on a trigger's effect immediately after its 202 and rely on the inline drain running before the response returns, which a concurrent monitor would turn into a race; the monitor's behaviour has its own tests and the Docker matrix.

### Demo gates name the hop (EDF-06)

`fvcv-handoff`'s ownership-transfer phase now gates on the CaseActor's own ledger holding `accept_case_ownership_transfer` (hop 1: trigger → CaseActor inbox → commit), read through the container that hosts the CaseActor, and only then checks the three replicas (hop 2: CaseActor outbox → each participant), all three against one shared budget with an EDF-06-008 comment.
The budget is the one the Finder check in the same phase already used; sharing it caps the phase's worst case at 90 s instead of 20 + 20 + 90, and a late replica is reported as the fan-out being late rather than as the transfer never having happened.
No timeout was widened.

### Consequences

- Good — a ledger fan-out reaches every replica in chain order on the normal path; forward-gap `Reject`s and their replays become what they were designed to be, recovery from loss.
- Good — a slow or unreachable recipient delays only its own rows (OX-01-006); the head-of-line hazard #3878 describes does not appear.
- Good — a transient delivery failure no longer reorders the failed row behind its successors (OX-13-012).
- Good — no schema change; the persistent queue API is unchanged.
- Neutral — a drain holds one *batch* (the queue as it stood when the pass looked) outside the persistent queue while the batch is delivered: the rows in flight and the rows waiting behind them in a busy lane. An unexpected error or a cancellation puts every undelivered row back before it propagates (`BatchInterrupted`); a hard process crash mid-batch loses the batch's undelivered rows — the same class of loss ADR-0066 accepted for the single in-flight row, widened to the batch. Narrowing it needs a claim/ack primitive on the queue, which is out of scope here.
- Neutral — order *across* recipients is not preserved and is not claimed; nothing in the protocol depends on it.
- Neutral — a row whose recipients cannot be resolved before delivery has no order guarantee; it also has no recipient to be ordered for.
- Neutral — `OutboxMonitor.drain_all` still visits actors sequentially, so a long drain of one actor under the lock delays the monitor's *safety-net* pass for the others; their own inbound-triggered drains are unaffected.
- Neutral — an inline drain that finds the slot held returns before the rows are delivered; a caller that needs the effect must observe it (EDF-06-001), not assume the 202 implied it.
- Good — in-memory stores are safe to use from a worker thread and the event loop at once, which every `TestClient`-driven test has done since #3883 moved the inbound BT off the loop.
- Good — production containers run the OX-09-002 safety-net drain for the first time; a row that no inline drain picks up is delivered within the monitor's poll interval instead of waiting for the next inbound activity.
- Good — every trigger route drains the outbox its emit actually landed in; three delegated emitters share one helper instead of one having the fix and two not.
- Deferred — whether the in-pass retry ladder should back off per recipient rather than per row is left to a future revision of ADR-0066.

## Generated Requirements

- `specs/outbox.yaml` OX-01-004, OX-01-005, OX-01-006, OX-13-012
- `specs/sync-ledger-replication.yaml` SYNC-15-012

## More Information

- Motivating issues: CERTCC/Vultron#3602 (transferor's replica late), CERTCC/Vultron#3878 (re-queue-at-tail reorders fan-out); hardened against recurrence of CERTCC/Vultron#3033 and CERTCC/Vultron#2898, whose triggers PR #3883 removed while the amplifier described here stayed.
- Evidence: CI runs 35917721682 (`fvcv-handoff`, 2026-09-23) and 33648494945 (`fv`, 2026-09-02).
- Retry envelope this ADR sits inside: ADR-0066.
- Receiver-side buffering this ADR stops exercising on the normal path: ADR-0037, ADR-0059.
- Implementation notes: `notes/outbox-delivery-reliability.md` § "Concurrent Drains Reorder a Fan-Out".
