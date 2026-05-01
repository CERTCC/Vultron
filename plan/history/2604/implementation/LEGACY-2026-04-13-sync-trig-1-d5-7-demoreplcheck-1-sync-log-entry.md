---
title: "SYNC-TRIG-1 + D5-7-DEMOREPLCHECK-1 \u2014 Sync Log Entry Trigger and\
  \ Finder"
type: implementation
timestamp: '2026-04-13T00:00:00+00:00'
source: LEGACY-2026-04-13-sync-trig-1-d5-7-demoreplcheck-1-sync-log-entry
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 5895
legacy_heading: "SYNC-TRIG-1 + D5-7-DEMOREPLCHECK-1 \u2014 Sync Log Entry\
  \ Trigger and Finder"
date_source: git-blame
---

## SYNC-TRIG-1 + D5-7-DEMOREPLCHECK-1 — Sync Log Entry Trigger and Finder

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:5895`
**Canonical date**: 2026-04-13 (git blame)
**Legacy heading**

```text
SYNC-TRIG-1 + D5-7-DEMOREPLCHECK-1 — Sync Log Entry Trigger and Finder
```

Replica Verification (COMPLETE 2026-04-14)

### SYNC-TRIG-1: `sync-log-entry` FastAPI trigger endpoint

Exposes `commit_log_entry_trigger` (already implemented in
`vultron/core/use_cases/triggers/sync.py`) via HTTP so demos and external
callers can exercise SYNC-2 log replication end-to-end.

- Created `vultron/adapters/driving/fastapi/routers/trigger_sync.py` with
  `POST /actors/{actor_id}/trigger/sync-log-entry`.
  - Request body: `SyncLogEntryRequest { case_id, object_id, event_type }`.
  - Response: `{ log_entry_id, entry_hash, log_index }`.
  - Resolves short `actor_id` path param to canonical URI before calling
    `commit_log_entry_trigger`.
  - Schedules `outbox_handler` as background task (consistent with other
    trigger endpoints).
- Added `SyncLogEntryRequest` to
  `vultron/adapters/driving/fastapi/trigger_models.py`.
- Registered `trigger_sync.router` in
  `vultron/adapters/driving/fastapi/routers/v2_router.py`.
- Created `test/adapters/driving/fastapi/routers/test_trigger_sync.py`
  (11 tests).

### D5-7-DEMOREPLCHECK-1: Finder replica verification in two-actor demo

Added Step 6 to `run_two_actor_demo` that:

1. Commits a log entry on the vendor via the new `sync-log-entry` trigger.
2. Polls the finder's DataLayer until the entry appears (proving SYNC-2
   replication).
3. Verifies four replica invariants: same case ID, matching
   `actor_participant_index` keys, same `active_embargo` ID, and at least
   one committed log entry in the finder's DataLayer.

New functions in `vultron/demo/two_actor_demo.py`:

- `trigger_log_commit()` — calls `POST /trigger/sync-log-entry`, returns
  `entry_hash`.
- `wait_for_finder_log_entry()` — polls `/datalayer/CaseLogEntrys/` with
  timeout.
- `_extract_ref_id()` — safely extracts string ID from
  `str | as_Link | EmbargoEvent | None` union.
- `_get_log_entries_for_case()` — filters DataLayer log entries by `case_id`.
- `verify_finder_replica_state()` — asserts four cross-actor invariants.

Added 3 test classes to `test/demo/test_two_actor_demo.py`:
`TestTriggerLogCommit`, `TestWaitForFinderLogEntry`,
`TestVerifyFinderReplicaState`.

**Files created**:

- `vultron/adapters/driving/fastapi/routers/trigger_sync.py`
- `test/adapters/driving/fastapi/routers/test_trigger_sync.py`

**Files modified**:

- `vultron/adapters/driving/fastapi/trigger_models.py`
- `vultron/adapters/driving/fastapi/routers/v2_router.py`
- `vultron/demo/two_actor_demo.py`
- `test/demo/test_two_actor_demo.py`

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` → 0 errors
- `uv run pyright` → 0 new errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1562 passed, 12 skipped, 5581 subtests passed`
