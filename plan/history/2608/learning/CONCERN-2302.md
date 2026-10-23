---
source: CONCERN-2302
timestamp: '2026-08-14T20:42:56.622096+00:00'
title: Outbox delivery retry limits compose into unbounded total — per-activity counter,
  4xx classification, dead-letter store
type: learning
---

## Context

CONCERN-2302 identified six defects in the outbound HTTP delivery path that
together allowed a permanently undeliverable activity to be retried
indefinitely:

1. `err_count` in `outbox_handler.py` is function-local and resets each drain
   pass — no cross-pass total-attempt bound.
2. Hardcoded `timeout=5.0` in `_deliver_with_retry` — too aggressive vs. 30 s
   demo client.
3. Bare `except Exception` retries 4xx responses as if transient.
4. No jitter on the `_deliver_with_retry` inner retry loop.
5. No `httpx.Limits` on `httpx.AsyncClient` — connection pool unbounded.
6. `err_count > 3: break` aborts the whole outbox drain rather than skipping
   the offending activity.

## Key Decisions (ADR-0066)

- **Option B chosen**: persisted per-activity `total_attempts` counter +
  dead-letter store on exhaustion (`max_total_attempts=12`).
- **4xx is terminal**: `httpx.HTTPStatusError` caught before bare `except
  Exception`; raises `DeliveryError` immediately — no retry slots consumed.
- **Abort scope**: `break` → `continue`; per-activity counter resets per
  activity so one failing activity cannot starve healthy ones.
- **Timeout, jitter, limits**: all made configurable on `HttpDeliveryAdapter`;
  default timeout raised to 30 s.
- **Protocol-level NACK deferred** to CERTCC/Vultron#1880.

## §7 Resolution

`outbox_handler.py`'s drain-loop abort does **not** silently drop outbox
entries — `outbox_pop()` removes, `outbox_append()` re-queues before `break`.
The severity is liveness/performance failure (healthy recipients delayed past
scenario timeout), not data-integrity loss.

## Outputs

- PR: <https://github.com/CERTCC/Vultron/pull/2314>
- ADR: `docs/adr/0066-outbox-terminal-state.md`
- Specs: `specs/outbox.yaml` (OX-13-001..006),
  `specs/sync-ledger-replication.yaml` (SYNC-05-004)
- Notes: `notes/outbox-delivery-reliability.md`
- Implementation Tasks: CERTCC/Vultron#2315 (abort-scope + 4xx),
  CERTCC/Vultron#2316 (timeout + jitter + limits),
  CERTCC/Vultron#2317 (attempt counter + dead-letter)
