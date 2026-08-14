---
status: accepted
date: 2026-08-14
deciders: Vultron maintainers
consulted: CERT/CC CVD research team
informed: Vultron contributors
---

# Outbox Terminal State: Per-Activity Attempt Counter, 4xx Classification, and Dead-Letter Store

## Context and Problem Statement

The outbound HTTP delivery path has retry limits at every layer, but they do not
compose into a bound on total delivery attempts. A permanently undeliverable activity
is retried indefinitely because the only cross-pass counter (`err_count` in
`outbox_handler.py`) is a function-local variable that resets on each drain pass;
there is no per-activity attempt count and no dead-letter destination.

Layered on top are four tuning defects: a 5 s POST timeout already rejected as
too aggressive elsewhere, retry-on-4xx (bare `except Exception`), no jitter on
the inner retry, and no connection-pool limits. Together these caused an 8,872-exception
connection storm in CI (`fccv-handoff` run 31732029289), and `err_count`'s abort
scope — breaking the whole outbox drain rather than skipping the offending activity —
delayed healthy ledger-entry deliveries past the scenario timeout.

This ADR decides:

1. How to give an undeliverable activity a finite total-attempt budget that
   survives drain-pass resets.
2. What happens when that budget is exhausted (dead-letter destination).
3. Whether 4xx responses should consume inner retry slots.
4. How to prevent one failing activity from blocking other activities in the same
   drain pass.
5. That the delivery timeout, retry parameters, and connection-pool limits become
   configurable on `HttpDeliveryAdapter`.

Source concern: CERTCC/Vultron#2302. See also CERTCC/Vultron#1880 (the analogous
inbound unprocessable-activity question — that concern's terminal-state answer SHOULD
be unified with this model in a future ADR).

## Decision Drivers

- **Bounded reliability envelope.** An unbounded retry is a runaway-resource condition;
  a protocol reference implementation must have a finite give-up condition.
- **Operator visibility.** Nothing currently distinguishes "not yet delivered" from
  "will never be delivered". Operators need a visible, queryable signal.
- **Delivery isolation.** One failing activity must not starve healthy activities.
- **Simplicity.** The model should require minimal new persistence primitives; the
  existing DataLayer `dead_letter` pattern (already used for inbound unresolvable
  objects) is the preferred anchor.
- **ADR-0042 is not in question.** HTTP-only delivery is settled; this ADR concerns
  the reliability envelope around that decision.

## Considered Options

### Option A — Discard on exhaustion (no dead letter)

Track attempts; when exhausted, log at CRITICAL and remove from the outbox queue.
Simplest implementation but loses the activity record permanently.

### Option B — Persisted attempt counter + dead-letter store (chosen)

Add an attempt count to the outbox queue entry (persisted with the entry so it
survives drain-pass resets). On exhaustion: move the activity to a dead-letter store
in the DataLayer, log at ERROR, stop requeueing. The dead-letter store is readable
by operators without log access.

### Option C — Protocol-level NACK on exhaustion

On exhaustion, send a protocol-level error notification to the activity's originator.
Addresses the analogous inbound question (CONCERN-2302 cross-references CERTCC/Vultron#1880
which asks exactly this). Out of scope here: the inbound terminal-state model is
unsettled and a joint decision would double scope. Deferred to #1880.

## Decision Outcome

Chosen option: **Option B — persisted attempt counter + dead-letter store.**

### Per-activity attempt counter (OX-13-001)

Each outbox queue entry tracks a `total_attempts` counter, persisted alongside the
activity ID in the queue. The counter is incremented on every delivery failure —
whether the failure occurs inside `_deliver_with_retry` (inner retry exhausted) or
is caught by `outbox_handler`'s per-pass error handling. The counter survives
`outbox_handler` invocations and reflects the activity's cumulative delivery history
across all drain passes.

### Maximum attempts and dead-letter (OX-13-002, OX-13-003, OX-13-004)

`max_total_attempts` is a configurable parameter (default: 12, chosen as
`(DEFAULT_MAX_RETRIES + 1) × ~3` drain passes — a budget that absorbs transient
failures without running indefinitely). When exhausted:

1. The activity is removed from the outbox queue.
2. It is written to a dead-letter store in the DataLayer (keyed by activity ID).
3. An ERROR-level log entry records the activity ID, failed recipients, and total
   attempt count.

Dead-letter entries are readable from the DataLayer so operators can inspect
exhausted activities without log access (OX-13-004).

**Protocol-level NACK**: out of scope in this ADR. If the protocol eventually
requires a terminal error notification (the question raised by #1880), that can be
layered onto exhaustion without changing the data model here.

### 4xx responses are terminal, not retryable (OX-13-005)

`HttpDeliveryAdapter._deliver_with_retry` catches `httpx.HTTPStatusError` separately
from connection/timeout errors. On a 4xx response, it raises `DeliveryError`
immediately without sleeping or consuming inner retry slots. Only HTTP 5xx,
connection errors (`httpx.ConnectError`, `httpx.ConnectTimeout`), and read timeouts
are retried with exponential backoff.

Rationale: a 422 Unprocessable Entity for a schema-invalid payload will never
succeed with the same payload; burning four retry attempts with backoff and then
requeueing indefinitely is a positive-feedback loop (more load → more 422s →
more retries → more load).

### Per-activity abort scope (OX-13-006)

`outbox_handler`'s per-pass error handling is restructured so that `err_count` is
reset after each activity (not per-pass). When an activity hits the per-pass cap:

- The current pass **continues** (`continue`, not `break`) — other activities in
  the queue are unaffected.
- The activity is re-appended to the queue tail for the next drain pass.

The per-pass cap is retained as a backstop against a single activity consuming all
delivery bandwidth in one pass; it is now per-activity rather than per-drain.

### Timeout, jitter, and connection-pool limits (SYNC-05-004)

`HttpDeliveryAdapter` gains a `timeout` constructor parameter (default 30 s,
replacing the hardcoded 5 s). `_deliver_with_retry` adds jitter
(`random.uniform(0, 0.5)` seconds) before each sleep to desynchronise retry waves
from fan-out failures. `emit()` constructs `httpx.AsyncClient` with
`httpx.Limits(max_connections=20, max_keepalive_connections=5)` to bound connection
pool growth.

### Consequences

- Good — every activity has a finite total-attempt budget visible to operators.
- Good — 4xx responses no longer consume retry budget or contribute to storms.
- Good — a single failing activity cannot delay healthy activities in the same pass.
- Good — delivery timeout, retry parameters, and pool limits are configurable from
  one construction site.
- Neutral — introduces a `total_attempts` field on outbox queue entries; existing
  entries without the field are treated as having `total_attempts = 0` (backward
  compatible).
- Deferred — protocol-level NACK on exhaustion, and the inbound terminal-state
  model (#1880), are not decided here.

## Generated Requirements

- `specs/outbox.yaml` OX-13-001 through OX-13-006
- `specs/sync-ledger-replication.yaml` SYNC-05-004

## More Information

- Source concern: CERTCC/Vultron#2302
- Inbound analogue (deferred): CERTCC/Vultron#1880
- Timeout consolidation coordination: CERTCC/Vultron#2202 AC-7
- Parent epic: CERTCC/Vultron#2231
- Implementation Tasks: CERTCC/Vultron#2303 (abort-scope + 4xx),
  CERTCC/Vultron#2304 (timeout + jitter + limits),
  CERTCC/Vultron#2305 (attempt counter + dead letter)
  *(issue numbers filled in after Tasks are created)*
