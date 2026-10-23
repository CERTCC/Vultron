---
source: CONCERN-720
timestamp: '2026-06-03T20:10:26.958367+00:00'
title: Adapter module names http_delivery.py and delivery_queue.py are inverted and
  misleading
type: learning
---

## Summary

`vultron/adapters/driven/http_delivery.py` and `vultron/adapters/driven/delivery_queue.py`
have inverted names relative to their actual roles. `delivery_queue.py` is the
real, working HTTP transport adapter (using `httpx` with retry/backoff).
`http_delivery.py` is a docstring-only stub for a future signed delivery adapter.
A developer or agent encountering both files will naturally assume `http_delivery.py`
is the live HTTP transport and `delivery_queue.py` is a queue abstraction —
the opposite of reality.

## Category

- Technical debt
- Fragile / high-churn area

## Severity

low

## Evidence

- `vultron/adapters/driven/http_delivery.py` — docstring-only stub; name implies it
  is the working HTTP transport
- `vultron/adapters/driven/delivery_queue.py` — working `DeliveryQueueAdapter` using
  `httpx`; name implies queue, not transport
- `vultron/adapters/driven/asgi_emitter.py` — imports `DeliveryQueueAdapter` as HTTP
  fallback, reinforcing the confusion

## Impact if Ignored

Agents and developers will misidentify the active delivery path, potentially
wrapping or replacing the wrong module. Issue #650 ingestion revealed this
confusion in real-time.

## Resolution

Root cause: inverted filenames cause systematic misidentification of the active
delivery path.

Fix: rename `delivery_queue.py` → `demo_http_delivery.py` (class
`DemoHttpDeliveryAdapter`) and `http_delivery.py` → `prod_http_delivery.py`
(class `ProdHttpDeliveryAdapter`, raises `NotImplementedError`). Update all
import sites, tests, specs, notes, and docs references.

**Resolved**: 2026-06-03 — implementation tracked in #721.
No docs PR (pure code rename; docs updates are part of the impl issue AC).
