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
related_notes:
  - notes/outbox.md
relevant_packages:
  - vultron/adapters/driven/http_delivery.py
  - vultron/adapters/driving/fastapi/outbox_handler.py
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

## Coordination Notes

- **#2202 AC-7**: that issue consolidates demo-side timeout constants. Once
  `HttpDeliveryAdapter.timeout` is configurable (Task C), #2202 can set it from
  a single config source rather than the hardcoded 5 s.
- **#1880**: inbound unprocessable activities — the analogous inbound terminal-state
  question. ADR-0066 defers the protocol-level NACK to that issue; the dead-letter
  store model should be unified when #1880 is planned.
- **OX-12-001**: HTTP-only delivery (ADR-0042) is not in question. All changes here
  are about the reliability envelope, not the delivery mechanism.
