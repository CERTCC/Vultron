---
title: Outbox Delivery Reliability
status: active
description: >
  Implementation guidance for the outbox delivery reliability hardening tasks:
  per-activity abort scope, 4xx terminal classification, timeout/jitter/pool
  configuration, and per-activity attempt counter with dead-letter store.
related_specs:
  - specs/outbox.yaml
  - specs/sync-ledger-replication.yaml
related_issues:
  - https://github.com/CERTCC/Vultron/issues/2302
  - https://github.com/CERTCC/Vultron/issues/2962
  - https://github.com/CERTCC/Vultron/issues/3602
  - https://github.com/CERTCC/Vultron/issues/3878
related_notes:
  - notes/outbox.md
  - notes/sync-ledger-replication.md
  - notes/flaky-tests.md
relevant_packages:
  - vultron/adapters/driven/http_delivery.py
  - vultron/adapters/driving/fastapi/outbox_handler.py
  - vultron/adapters/driving/fastapi/outbox_lanes.py
  - vultron/adapters/driven/sync_activity_adapter.py
  - vultron/adapters/driven/datalayer_sqlite/engine.py
---

# Outbox Delivery Reliability

Implementation guidance for CONCERN-2302 remediation. See ADR-0066 for the
architectural rationale and option analysis.

---

## Per-Pass Cap: Queue Tail Is Still This Pass (OX-13-011)

**Trap**: `outbox_handler`'s drain loop is `while outbox_list()`.
When a failed activity is re-queued, it lands at the tail of the
*current* pass, not the next one.
A cap check that only prevents further attempts after the fact (without
removing the item from the queue) lets the activity be popped again in the
same pass.

**Fix**: record capped activities in an in-memory `capped_this_pass` set.
When the loop pops an item in that set, re-queue it immediately without
attempting delivery and without incrementing the attempt counter, then
`continue`.
The activity stays in the persistent queue throughout (a crash mid-pass
cannot lose it), and the next drain pass starts fresh with no `capped_this_pass`
set.

**Why not hold capped items in memory and re-queue after the loop?**
A crash mid-pass discards the in-memory set, and those activities are not in
the persistent queue.
The queue tail is a safe holding area because the loop ends when every queued
item is in `capped_this_pass` — the re-queued skips are a no-op until then.

**Impact on the dead-letter budget**: the `MAX_TOTAL_ATTEMPTS` constant (12 by
default) is a cross-pass total.
Extra attempts within one pass from the ordering bug consume that budget faster
than the documented `(DEFAULT_MAX_RETRIES + 1) × ~3 drain passes` formula
assumes.
Fixing the ordering restores the intended budget.

See ADR-0066 § "Per-activity abort scope" for the full rationale.
Source: CONCERN-2962.

---

## Concurrent Drains Reorder a Fan-Out; Lanes Restore Per-Recipient Order (ADR-0112)

**Trap**: `outbox_handler` is called after *every* inbound activity
(`inbox_orchestration.run_inbox_pipeline`), from the legacy inbox handler, and
from `OutboxMonitor.drain_all`. Before ADR-0112 nothing serialized those calls.
Each concurrent drain popped the next row of the same FIFO and awaited its
POST, so rows *completed* delivery in an order unrelated to enqueue order —
run 35917721682 had 28 in flight at once from the CASE_MANAGER's outbox, and a
14-row backfill popped `0…13` reached its peer as `4, 7, 1, 8, 5, 2, 10, 6, 11,
13, 12, 9, 3`. Every forward gap is a `Reject` (SYNC-14-002); every `Reject` at
an advanced position is a full-suffix replay (SYNC-15-010); every replay lands
in the same queue ahead of the next entry's fan-out to every other peer. The
`Announce` of entry 15 to Vendor1 waited 14.4 s *in the queue* — not in flight —
behind 77 replay rows addressed to the Coordinator (#3602). The `fv` and `fcvcv`
failures (#3033, #2898) show the same loop; PR #3883 removed their emission-order
*triggers* and left the drain alone.

**Do not** read "OX-01-002 FIFO" as a delivery guarantee: it was a property of
the queue, and `test_outbox_handler_preserves_fifo_order` recorded *pop* order
from a single drain. Pop order is not what a recipient sees.

**Fix** (ADR-0112): `outbox_handler` takes a per-actor drain lock (OX-01-004,
registry keyed by event loop like `_actor_inbox_locks`) and hands each popped
batch to `outbox_lanes.deliver_batch`, which runs rows in per-recipient lanes —
at most one in-flight row per recipient, recipients concurrently (OX-01-005,
OX-01-006). A row's lanes are its recipients, resolved with `lane_keys()`
before delivery; an unreadable or recipient-less row gets a lane of its own.
The ratchet `test/architecture/test_outbox_drain_under_actor_lock.py` keeps
every drain caller behind the lock.

**Re-queue keeps the lane's order (#3878, OX-13-012)**: a row that fails past
the per-pass cap *stalls* its lanes. Nothing behind it in those lanes is
attempted that pass, and the held rows are appended back in `StallOrder` — the
order they were first held, i.e. enqueue order — so the queue the pass leaves is
each lane's enqueue order without any head-insert primitive. The drain keeps
that order for the whole pass, so a row a producer appends mid-pass, popped in
a later batch into a stalled lane, is placed behind the rows stalled before it.
Rows in *other* lanes are untouched: this is not head-of-line blocking.

**Replay dedup (SYNC-15-012)**: `SyncActivityAdapter.send_announce_log_entry`
returns `False` and queues nothing when an `Announce` of that entry to that
peer is already pending in the outbox; `SendMissingEntriesNode` counts only
`True` as sent (SYNC-15-011). The outbox read is the adapter's, not the
node's — core must not read activities back (DL-06-001). SYNC-15-010 stands —
the `Reject` still replays — it just cannot queue the same row twice. Defense in depth: a
`Reject` delayed in the *peer's* outbox can still arrive after the gap drained.

**Skip, do not wait, when the slot is held.** The first version made a second
caller `await` the lock and the multi-app handoff test hung: under Starlette's
`TestClient` a recipient's BackgroundTask runs *inside* the sender's POST, so a
round-trip delivery re-enters `outbox_handler` for the same actor while the
outer drain awaits that POST. A held slot now gets a "look once more" flag and
the caller returns; the holder re-reads the queue before finishing. Production
never nests (202 precedes the task), but a drain policy must not have a
deadlock class.

**Lanes exposed a store race in tests (in-memory `StaticPool`).** Concurrent
deliveries mean the CaseActor's inbox worker thread and its outbox drain on the
loop use the CaseActor's store at once. An in-memory store has *one* connection
shared by every `Session` (`StaticPool`, `check_same_thread=False`) and the pool
rolls it back on checkin — so one thread's `Session.close()` discarded another's
uncommitted insert: a just-stored `Reject` read back as "not found", was
dropped, and the peer's buffered entry never drained (2/4 `test_fv_demo.py`
runs). `SqliteDataLayer._session()` now serializes every adapter session per
engine (`engine.session_guard`); do not open `Session(dl._engine)` directly.
Do not hang the lock on pool checkout/checkin events: two fairies on
`StaticPool`'s one record make a checkin go missing.

**Demo gates** (EDF-06): gate on the CaseActor's own ledger holding the entry
(`wait_for_case_actor_ledger_event`, hop 1), then check the replicas against
one `SharedBudget` (hop 2). A late replica then reads as "fan-out late", not
"transfer never happened". Never widen a replica wait to cover the queue.

Sources: #3602, #3878; CI runs 35917721682 (`fvcv-handoff`) and 33648494945
(`fv`).

---

## Coordination Notes

- **#2202 AC-7**: that issue consolidates demo-side timeout constants. Once
  `HttpDeliveryAdapter.timeout` is configurable (Task C), #2202 can set it from
  a single config source rather than the hardcoded 5 s.
- **#1880**: inbound unprocessable activities — the analogous inbound terminal-state
  question. ADR-0066 defers the protocol-level NACK to that issue; the dead-letter
  store model should be unified when #1880 is planned.
- **OX-12-001**: HTTP-only delivery (ADR-0042) is not in question. All changes here
  are about the reliability envelope, not the delivery mechanism.
