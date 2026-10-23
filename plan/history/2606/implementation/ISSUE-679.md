---
source: ISSUE-679
timestamp: '2026-06-03T21:08:38.145424+00:00'
title: Event-driven wakeup for OutboxMonitor
type: implementation
---

## Issue #679 — Event-driven wakeup for OutboxMonitor

Replaced the fixed-interval `asyncio.sleep` polling loop in `OutboxMonitor`
with an event-driven wakeup mechanism via callback injection, satisfying
specs OX-09-001, OX-09-002, OX-09-003.

### Changes

**`vultron/adapters/driven/datalayer_sqlite.py`**

- Added optional `enqueue_callback: Callable[[str], None]` constructor param
  and `set_enqueue_callback()` setter.
- `clone_for_actor()` inherits parent callback so actor-scoped DL instances
  are covered without explicit re-registration.
- `outbox_append()` and `record_outbox_item()` invoke callback after DB
  commit, guarded with `try/except` so callback failures never abort the
  enqueue.

**`vultron/adapters/driving/fastapi/outbox_monitor.py`**

- New fields: `_wakeup_event`, `_loop`, `_registered_actors`.
- New methods: `_notify()` (uses `loop.call_soon_threadsafe` for thread
  safety since sync handlers run in thread-pool executors) and
  `_register_new_actors()`.
- `_run_loop()` replaced with `asyncio.wait_for(event.wait(), timeout=poll_interval)`
  pattern plus safety-net fallback.
- `start()` creates `asyncio.Event` and captures the running loop.
- `stop()` clears `_loop` and `_registered_actors` but preserves
  `_wakeup_event` to avoid a cancel/set race.

### Tests

Added ~20 new tests across `test_outbox_monitor.py` and
`test_sqlite_backend.py` covering: wake-on-enqueue, safety-net poll,
callback roundtrip, `_register_new_actors` behavior, `stop()` cleanup,
clone inheritance, exception guard, and setter replace. All 2637 existing
tests continue to pass.

PR: [#735](https://github.com/CERTCC/Vultron/pull/735)
