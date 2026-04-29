---
title: 'ACT-2: Per-Actor DataLayer Isolation (ADR-0012)'
type: implementation
date: '2026-03-24'
source: ACT-2
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3071
legacy_heading: 'ACT-2: Per-Actor DataLayer Isolation (ADR-0012)'
date_source: git-blame
---

## ACT-2: Per-Actor DataLayer Isolation (ADR-0012)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3071`
**Canonical date**: 2026-03-24 (git blame)
**Legacy heading**

```text
ACT-2: Per-Actor DataLayer Isolation (ADR-0012)
```

**Priority**: 100 (highest open task at time of implementation)

### Summary

Implemented Option B (TinyDB namespace prefix per actor) from ADR-0012.
Each actor's tables are prefixed `{actor_id}_*` in the same TinyDB file.
Activity objects are stored in the shared DataLayer for cross-actor
accessibility; inbox/outbox queues are in the actor-scoped DataLayer.

### Key design decisions

- **Activity objects → shared DL**: All activities are stored in the shared
  (unprefixed) DataLayer so rehydration and cross-actor use cases work.
- **Inbox/outbox queues → actor-scoped DL**: Queue records hold only the
  `activity_id` string in `{actor_id}_inbox` / `{actor_id}_outbox` tables.
- **Inbox visibility record → actor object in shared DL**: `post_actor_inbox`
  also appends the activity ID to `actor.inbox.items` in the shared DL actor
  record (persistent received-log, never cleared by the handler).
- **`_shared_dl()` wrappers**: Prevent FastAPI from injecting the `actor_id`
  path parameter into `get_datalayer()` calls in all routers.
- **`_actor_dl()` in trigger routes returns shared DL**: Trigger use cases
  need the shared DL (actors, offers, reports are all there).

### Files modified

- `vultron/adapters/driven/datalayer_tinydb.py`: actor_id prefix, `_my_tables()`,
  inbox/outbox methods, `get_datalayer(actor_id)` factory, `reset_datalayer()`
- `vultron/core/ports/datalayer.py`: 6 inbox/outbox Protocol methods
- `vultron/adapters/driving/fastapi/inbox_handler.py`: accepts `actor_dl` param
- `vultron/adapters/driving/fastapi/outbox_handler.py`: uses `dl.outbox_list/pop`
- `vultron/adapters/driving/fastapi/routers/actors.py`: `_shared_dl()`, inbox
  visibility record update, actor-scoped queue management
- `vultron/adapters/driving/fastapi/routers/datalayer.py`: `_shared_dl()`
- `vultron/adapters/driving/fastapi/routers/trigger_{report,case,embargo}.py`:
  `_actor_dl()` returns shared DL
- `vultron/demo/utils.py`: `init_actor_ios()` is no-op
- `test/adapters/driven/test_datalayer_isolation.py`: 26 new isolation tests

### Test results

1014 passed, 5581 subtests passed.
