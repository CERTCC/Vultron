---
source: CONCERN-503
timestamp: '2026-06-02T20:28:29.409378+00:00'
title: Outbox drain loop uses fixed 1-second polling over all actor DataLayers
type: learning
---

## Summary

The `OutboxMonitor` polls all registered actor-scoped `DataLayer` instances once per
second regardless of queue depth. Polling cost grows linearly with actor count and
can mask queue-depth problems.

## Category

- Top risk
- Performance / scaling

## Severity

medium

## Evidence

- `vultron/adapters/driving/fastapi/outbox_monitor.py`

## Impact if Ignored

More actors mean more unnecessary wakeups and DataLayer reads per second, and
queue-depth issues become harder to observe.

## Suggested Action

Consider event-driven wakeups (e.g., an asyncio Event set on enqueue) or adaptive
polling with backoff; add queue-depth metrics if actor count grows beyond demo scale.

## Resolution

**Resolved**: 2026-06-02 — root cause confirmed as O(N) idle DataLayer iteration on
every tick. Agreed approach: callback injection pattern — `SqliteDataLayer.outbox_add()`
accepts an optional `enqueue_callback: Callable[[str], None]`; `OutboxMonitor` owns an
`asyncio.Event`, provides `_notify()` as the callback, and uses
`asyncio.wait_for(event.wait(), timeout=poll_interval)` instead of bare
`asyncio.sleep`. Safety-net polling retained. Spec updated with OX-09 "Outbox Monitor
Efficiency" group (OX-09-001 through OX-09-005).

Docs PR: [#681](https://github.com/CERTCC/Vultron/pull/681).
Implementation tracked in [#679](https://github.com/CERTCC/Vultron/issues/679)
(event-driven wakeup) and [#680](https://github.com/CERTCC/Vultron/issues/680)
(queue-depth observability, blocked by #679).
