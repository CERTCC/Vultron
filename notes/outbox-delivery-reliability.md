---
title: Outbox Delivery Reliability
status: active
kind: guidance
description: >
  Rules for outbox delivery reliability: per-pass caps and the queue tail,
  per-recipient lanes under a per-actor drain lock, batch interruption, store
  sessions under concurrent delivery, retry budgets that must stay finite,
  immediate dead-lettering of a refused sealed body (OX-13-013),
  request-derived ids for responses, the outbox-id idempotency check
  (OX-06-002), and why the send-then-commit order (SYNC-09-002) makes a derived
  id mandatory for a send a retry can rebuild, and a withdrawal mandatory for
  one no retry rebuilds.
related_specs:
  - specs/outbox.yaml
  - specs/sync-ledger-replication.yaml
related_issues:
  - https://github.com/CERTCC/Vultron/issues/2302
  - https://github.com/CERTCC/Vultron/issues/3602
  - https://github.com/CERTCC/Vultron/issues/3878
  - https://github.com/CERTCC/Vultron/issues/4215
  - https://github.com/CERTCC/Vultron/issues/4158
related_notes:
  - notes/outbox.md
  - notes/sync-ledger-replication.md
  - notes/flaky-tests.md
  - notes/testing-pitfalls.md
  - notes/case-ledger-authority.md
relevant_packages:
  - vultron/adapters/driven/http_delivery.py
  - vultron/adapters/driving/fastapi/outbox_handler.py
  - vultron/adapters/driving/fastapi/outbox_lanes.py
  - vultron/adapters/driven/sync_activity_adapter.py
  - vultron/adapters/driven/datalayer_sqlite/engine.py
  - vultron/adapters/driving/fastapi/main.py
  - vultron/adapters/driving/fastapi/routers/trigger_actor.py
  - vultron/adapters/driven/datalayer_sqlite/queues.py
  - vultron/core/models/activity_ids.py
---

# Outbox Delivery Reliability

ADR-0066 holds the reliability design; ADR-0112 the per-recipient ordering.

---

## Per-Pass Cap: Queue Tail Is Still This Pass (OX-13-011)

The drain loops while the outbox is non-empty, so a re-queued row lands at the tail of
the *current* pass and is popped again in it. A cap that only counts attempts therefore
lets a row exceed it within one pass and burn the cross-pass `MAX_TOTAL_ATTEMPTS`
budget early. A row past `MAX_PER_PASS_ATTEMPTS` is *stalled* for the pass, and the
pass ends once every pending row is stalled (`StallOrder.covers`). Stalled rows stay in
the persistent queue, so a crash mid-pass cannot lose them; do not hold them in memory
to re-queue after the loop.

---

## Concurrent Drains Reorder a Fan-Out; Lanes Restore Per-Recipient Order (ADR-0112)

`outbox_handler` runs after every inbound activity, from the legacy inbox handler, and
from `OutboxMonitor.drain_all`. Unserialized, concurrent drains each popped the next
FIFO row and awaited its POST, so rows *completed* in an order unrelated to enqueue
order; every forward gap at a peer is a `Reject` (SYNC-14-002) and every `Reject` a
suffix replay (SYNC-15-010) queued ahead of the next fan-out (#3602). **OX-01-002 FIFO
is a property of the queue's pop order, not a delivery guarantee.**

- **One drain per actor, rows in per-recipient lanes.** `outbox_handler` takes a
  per-actor drain lock (OX-01-004) and hands each popped batch to
  `outbox_lanes.deliver_batch`: at most one in-flight row per recipient, recipients
  concurrently (OX-01-005/006). A row's lanes are its recipients (`lane_keys()`); an
  unreadable or recipient-less row gets a lane of its own. The ratchet
  `test/architecture/test_outbox_drain_under_actor_lock.py` keeps every drain caller
  behind the lock. The slot is keyed on the store's canonical id (`actor.id_`), since
  trigger routes pass a short id and the inbox path the URI.
- **A stall keeps the lane's order (OX-13-012).** A stalled row stops its lanes for the
  pass; held rows go back in `StallOrder`, i.e. enqueue order, including rows appended
  mid-pass. Other lanes are untouched, so this is not head-of-line blocking (#3878).
- **A batch lives outside the queue while it is delivered.** On an escaping exception or
  cancellation, `deliver_batch` cancels in-flight tasks and raises
  `BatchInterrupted(undelivered)`, and `_drain_outbox` re-appends every undelivered row
  before re-raising (a cancellation as itself, so `OutboxMonitor.stop()` still stops).
  `_deliver_row` never raises on its own. A hard process crash mid-batch loses the
  batch's undelivered rows; say so rather than claiming otherwise.
- **Replay dedup (SYNC-15-012).** `SyncActivityAdapter.send_announce_log_entry` returns
  `False` and queues nothing when an `Announce` of that entry to that peer is already
  pending; `SendMissingEntriesNode` counts only `True` as sent (SYNC-15-011). The read
  is the adapter's, not the node's (DL-06-001).
- **Skip, do not wait, when the slot is held.** Under `TestClient` a recipient's
  BackgroundTask runs inside the sender's POST, so a round-trip re-enters
  `outbox_handler` for the same actor while the outer drain awaits; an `await` on the
  lock deadlocks. A held slot sets a "look once more" flag and the caller returns; the
  holder re-reads the queue before finishing.
- **Concurrent delivery needs serialized store sessions.** An in-memory store shares
  one connection across every `Session` (`StaticPool`) and rolls it back on checkin, so
  one thread's `close()` discards another's uncommitted insert.
  `SqliteDataLayer._session()` serializes sessions per engine (`engine.session_guard`):
  never open `Session(dl._engine)` directly, and do not hang the lock on pool
  checkout/checkin events.
- **When you serialize a queue, audit who relied on the churn.** Serializing the drain
  exposed rows that only ever moved because some concurrent drain happened to pick them
  up: every trigger route now drains the outbox the delegated emit went into
  (`emitting_outbox()` in `trigger_runner.py`, CM-24-001), and the root app shares
  `_make_lifespan` so the `OutboxMonitor` safety-net poll (OX-09-002) actually runs.
- **Demo gates** (EDF-06): gate on the CaseActor's own ledger holding the entry
  (`wait_for_case_actor_ledger_event`), then check the replicas against one
  `SharedBudget`, so a late replica reads as "fan-out late", not "transfer never
  happened". Never widen a replica wait to cover the queue.

---

## Retry Caps That Compose into an Unbounded Total (OX-13-001, OX-13-002)

Before shipping a delivery retry change, check that
`inner_retries × per_pass_cap × requeue_cadence` is finite. A bounded inner retry
(`max_retries + 1 = 4`), a per-pass error count reset on every drain, and an
unconditional requeue compose to `4 × ∞`. The fix is a persisted per-activity
total-attempt counter with a give-up condition (ADR-0066).

## A Refused Sealed Body Is Dead-Lettered at Once (OX-13-013)

The retry budget is for failures a retry can cure. A body the outbox refuses before any
delivery attempt — a `to:` naming no one (OX-08-003), a non-inline `object`
(OX-07-001) — is refused identically every time, because the sealed body never changes
(VM-08-003). `_bookkeep_failure` dead-letters those rows (`UNDELIVERABLE_BODY_ERRORS`)
on the first refusal with reason `undeliverable_body`. Fix the producer too: an
activity addressed to no one is not queued at all (OX-08-001). See
[testing-pitfalls](testing-pitfalls.md) § "A Retry Loop With Real Backoff Hides Inside
a Passing Demo".

---

## A Response to an Inbound Activity Takes Its Id From the Request

An outbound activity answering one inbound activity (a `ProcessingFault` NACK,
`Reject(CaseLedgerEntry)`, `Accept(CaseProposal)`) MUST NOT mint a fresh UUID per
emission, or every redelivery grows the store and outbox (ID-04-004, #4215).

- Derive the id with `derived_activity_id(kind, actor, <what it answers>, ...)` in
  `vultron/core/models/activity_ids.py`, kind label first so two kinds of response
  to one activity never collide. Core derives too: the stub Invite answering an
  owner's `Offer(Actor, Case)` takes its id from that Offer.
- Ask "was this already sent?" with `is_sealed(dl, id)`: the sealed body outlives the
  outbox entry, so it still answers after delivery popped the queue (see
  `notes/bt-pitfalls.md` § "A Refusal Arm in a Selector Fails Toward 'Admit'").
- Treat "sealed" as "built", not "sent". The sealed body is written before the queue
  append, so queue the same id and body again and let the receiver deduplicate
  (ID-04-005); skipping on "sealed" alone loses the response after a crash between the
  two writes. `requeue_if_sealed` in `vultron/adapters/outbox_sealed_body.py` does both.
- A sent act is committed after its outbox write (SYNC-09-002, ADR-0119), so the
  outbox is the only thing that stops a retry sending it again. A retry that rebuilds
  the activity under a fresh id defeats it: any emit node whose tree can run again
  after its commit failed — a redelivered request, a resumed tree, a level-triggered
  node — MUST derive the id. A node that cannot tell from the store that its send
  is unrecorded (the stub re-issue reads stored Invites) must look for the sent,
  unrecorded activity itself and commit it (`ReissueStubInvitesNode`).
- A send that no retry rebuilds (the embargo teardown, which its own EM write stops
  from rerunning; the manager's own proposal relay) MUST withdraw the activity with
  `outbox_withdraw` when its commit fails, then raise: left pending it reaches
  participants with no entry recording it (CLP-07-013). See
  `_CommitCaseManagerActivityBase._withdraw_unrecorded`.
- A commit that fails after the outbox write MUST escape the node, never return
  FAILURE: an enclosing Selector would read it as a guard miss and send another
  arm's answer after the queued one (BT-14-001; `_EmitSingleActivityBase.update`).
- Call `outbox_append` and read its result; never test `id in outbox_list()` first.
  The append itself leaves a pending id alone (OX-06-002), atomically, and returns
  `False`. It only sees what is pending: a delivered id is queued again.
  A partial UNIQUE index on outbox rows of `vultron_queue` backs it, so the store
  itself refuses a duplicate pending id, and a store without the index is refused
  at open (#4629). The inbox is not covered: it has no no-duplicate rule.
- A rebuilt activity carries its first attempt's sealed body, so its first
  `published`. `CreateLogEntryNode` therefore reuses an equivalent recorded entry
  before the claimed-timestamp guard runs; checking first would refuse a late retry
  as stale (CLP-14-008) for an act the ledger already holds.
- A spec that answers a duplicate request by re-sending the stored response (CP-05-006)
  is the same rule: reuse the id and sealed body, re-queue only when not pending.
