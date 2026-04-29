---
title: "ACT-3 \u2014 Per-actor DataLayer for trigger endpoints (2026-03-25)"
type: implementation
date: '2026-03-25'
source: ACT-3
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3179
legacy_heading: "ACT-3 \u2014 Per-actor DataLayer for trigger endpoints (2026-03-25)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-25'
---

## ACT-3 — Per-actor DataLayer for trigger endpoints (2026-03-25)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3179`
**Canonical date**: 2026-03-25 (git blame)
**Legacy heading**

```text
ACT-3 — Per-actor DataLayer for trigger endpoints (2026-03-25)
```

**Legacy heading dates**: 2026-03-25

**Task**: Update `get_datalayer` dependency and all handler tests to use
per-actor DataLayer fixtures (ADR-0012 DI-1 closure lambda strategy).

### What was done

- Updated `_actor_dl` FastAPI dependency in all three trigger routers to call
  `get_datalayer(actor_id)` instead of the shared `get_datalayer()`:
  - `vultron/adapters/driving/fastapi/routers/trigger_case.py`
  - `vultron/adapters/driving/fastapi/routers/trigger_report.py`
  - `vultron/adapters/driving/fastapi/routers/trigger_embargo.py`
- Refactored trigger test fixtures in all three test files to use a combined
  `actor_and_dl` fixture that creates the actor in-memory first, then
  instantiates a `TinyDbDataLayer(db_path=None, actor_id=actor.as_id)` scoped
  to that actor's ID, and persists the actor into it.  The `actor` and `dl`
  fixtures unpack from `actor_and_dl`.
- Updated `test_trigger_validate_report_uses_injected_datalayer` to use the
  per-actor `dl` fixture instead of the shared `datalayer` fixture.
- Removed unused `object_to_record` import from `test_trigger_report.py`.

### Lessons learned

- The "actor before DataLayer" combined-fixture pattern (`actor_and_dl`) solves
  the chicken-and-egg problem of needing the actor's `as_id` to create a
  scoped DataLayer, while still allowing all downstream fixtures to depend on
  both `actor` and `dl` independently.
- The `client_triggers` override `lambda: dl` continues to work after the
  production change because FastAPI `dependency_overrides` replaces the entire
  dependency callable, bypassing the `actor_id = Path(...)` parameter.

### Test results

998 passed, 5581 subtests passed.
