---
title: "D5-6-TRIGDELIV \u2014 Fix trigger endpoints to deliver outbox activities\
  \ (2026-04-07)"
type: implementation
date: '2026-04-07'
source: D5-6-TRIGDELIV
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 4806
legacy_heading: "D5-6-TRIGDELIV \u2014 Fix trigger endpoints to deliver outbox\
  \ activities (2026-04-07)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-07'
---

## D5-6-TRIGDELIV — Fix trigger endpoints to deliver outbox activities (2026-04-07)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:4806`
**Canonical date**: 2026-04-07 (git blame)
**Legacy heading**

```text
D5-6-TRIGDELIV — Fix trigger endpoints to deliver outbox activities (2026-04-07)
```

**Legacy heading dates**: 2026-04-07

**Root cause**: All nine trigger endpoints (`trigger_report.py`,
`trigger_case.py`, `trigger_embargo.py`) executed the use case and returned
202, but never scheduled `outbox_handler` as a `BackgroundTask`. Activities
queued by the use cases via `add_activity_to_outbox` → `record_outbox_item`
remained in the delivery queue indefinitely.

**Fix**: Added `BackgroundTasks` as a dependency to all nine trigger endpoint
functions and scheduled `outbox_handler(actor_id, get_datalayer(actor_id), dl)`
as a background task after each successful use-case execution. The actor-scoped
DataLayer (`get_datalayer(actor_id)`) manages the outbox queue; the shared DL
(`dl` from `Depends(_actor_dl)`) is passed as `shared_dl` for activity object
lookup. This matches the pattern used by `post_actor_outbox` in `actors.py`.

**Tests added**: `TestTriggerReportOutboxScheduling` (3 tests),
`TestTriggerCaseOutboxScheduling` (2 tests),
`TestTriggerEmbargoOutboxScheduling` (3 tests) — each patches `outbox_handler`
with `AsyncMock` and `get_datalayer` with `MagicMock`, then verifies the mock
was called with the correct `actor_id` and DataLayer after a successful trigger
request.

**Files changed**:

- `vultron/adapters/driving/fastapi/routers/trigger_report.py`
- `vultron/adapters/driving/fastapi/routers/trigger_case.py`
- `vultron/adapters/driving/fastapi/routers/trigger_embargo.py`
- `test/adapters/driving/fastapi/routers/test_trigger_report.py`
- `test/adapters/driving/fastapi/routers/test_trigger_case.py`
- `test/adapters/driving/fastapi/routers/test_trigger_embargo.py`
