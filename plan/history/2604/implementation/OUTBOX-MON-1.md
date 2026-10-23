---
title: "OUTBOX-MON-1 \u2014 OutboxMonitor background loop"
type: implementation
timestamp: '2026-04-11T00:00:00+00:00'
source: OUTBOX-MON-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 5631
legacy_heading: "OUTBOX-MON-1 \u2014 OutboxMonitor background loop (COMPLETE\
  \ 2026-04-11)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-11'
---

## OUTBOX-MON-1 — OutboxMonitor background loop

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:5631`
**Canonical date**: 2026-04-11 (git blame)
**Legacy heading**

```text
OUTBOX-MON-1 — OutboxMonitor background loop (COMPLETE 2026-04-11)
```

**Legacy heading dates**: 2026-04-11

**Task**: Implement a background outbox-drain loop (OUTBOX-MON-1) that
periodically scans all registered actor-scoped DataLayer instances and
delivers pending outbox activities to recipient inboxes automatically,
without requiring a manual trigger.

**Files changed**:

- `vultron/adapters/driven/datalayer_tinydb.py`: Added
  `get_all_actor_datalayers()` factory function that returns a snapshot of
  the `_datalayer_instances` dict (all registered actor-scoped DataLayer
  instances).
- `vultron/adapters/driving/fastapi/outbox_monitor.py` (new): `OutboxMonitor`
  class with `drain_all()` async method, `_run_loop()` polling loop, and
  `start()` / `stop()` lifecycle methods. Polls every 1 second by default.
  Accepts injected `actor_datalayers_factory`, `shared_dl`, and `emitter`
  for testability.
- `vultron/adapters/driving/fastapi/app.py`: Updated `lifespan` to
  instantiate `OutboxMonitor`, call `monitor.start()` on startup and
  `monitor.stop()` on shutdown.
- `test/adapters/driving/fastapi/test_outbox_monitor.py` (new): 19 unit
  tests covering `drain_all()` (empty/non-empty outboxes, multi-actor,
  error handling, default factory, default shared_dl), and `start()`/`stop()`
  lifecycle (task creation, cancellation, double-start warning, restart).

**Design notes**:

- `drain_all()` resolves `get_all_actor_datalayers` lazily at call time (not
  captured at `__init__`) so that test patches targeting the module-level
  name are effective.
- Error handling: per-actor exceptions are caught and logged at ERROR level;
  other actors' outboxes continue to be processed.
- `asyncio.CancelledError` is caught in `_run_loop()` so the monitor stops
  cleanly when cancelled via `stop()`.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 new errors (11 pre-existing pyright
  errors in `test_note_trigger.py` unchanged)
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1447 passed, 10 skipped, 5581 subtests passed in 81.35s`
