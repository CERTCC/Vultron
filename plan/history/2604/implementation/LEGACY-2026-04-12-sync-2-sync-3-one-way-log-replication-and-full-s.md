---
title: "SYNC-2 + SYNC-3 \u2014 One-way log replication and full sync loop\
  \ with retry/backoff"
type: implementation
timestamp: '2026-04-12T00:00:00+00:00'
source: LEGACY-2026-04-12-sync-2-sync-3-one-way-log-replication-and-full-s
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 5798
legacy_heading: "SYNC-2 + SYNC-3 \u2014 One-way log replication and full sync\
  \ loop with retry/backoff"
date_source: git-blame
---

## SYNC-2 + SYNC-3 — One-way log replication and full sync loop with retry/backoff

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:5798`
**Canonical date**: 2026-04-12 (git blame)
**Legacy heading**

```text
SYNC-2 + SYNC-3 — One-way log replication and full sync loop with retry/backoff
```

**Completed**: 2026-04-14

**Tasks**: SYNC-2, SYNC-3 (Priority 330)

**Summary**: Implemented one-way log replication from CaseActor to Participant
Actors via AS2 `Announce(CaseLogEntry)` activities (SYNC-2), and full sync loop
with retry/backoff and hash-mismatch conflict resolution via
`Reject(CaseLogEntry)` activities (SYNC-3).

### SYNC-2: One-way log replication

- Added `AnnounceLogEntryReceivedUseCase` in
  `vultron/core/use_cases/received/sync.py` that:
  - Validates `prev_log_hash` chain continuity (SYNC-03-001).
  - Appends the `CaseLogEntry` to the local log if the chain is valid.
  - Rejects (sends `Reject(CaseLogEntry)` with `context` set to
    last-accepted hash) on mismatch (SYNC-03-001, SYNC-03-002).
  - Is idempotent: duplicate hashes are silently ignored (SYNC-03-003).
- Added `AnnounceLogEntryActivity` in
  `vultron/wire/as2/vocab/activities/sync.py`.
- Added `AnnounceLogEntryPattern` in `vultron/wire/as2/extractor.py`.
- Added `ANNOUNCE_CASE_LOG_ENTRY` to `MessageSemantics` and registered
  `AnnounceLogEntryReceivedEvent` in `vultron/core/models/events/`.
- Added `announce_log_entry_trigger` in
  `vultron/core/use_cases/triggers/sync.py` for CaseActor-initiated fan-out
  to all participants.

### SYNC-3: Full sync loop with retry/backoff

- Added `RejectLogEntryReceivedUseCase` that:
  - Reads the `last_accepted_hash` from the rejection `context` field
    (falls back to `GENESIS_HASH`).
  - Persists per-peer `VultronReplicationState` (new model in
    `vultron/core/models/replication_state.py`).
  - Queues replay of all missing entries after `last_accepted_hash` via
    `replay_missing_entries_trigger`.
- Added `replay_missing_entries_trigger` in
  `vultron/core/use_cases/triggers/sync.py` that iterates the local log
  from `from_hash` onward and re-emits `AnnounceLogEntry` for each entry.
- Implemented delivery retry/backoff in
  `vultron/adapters/driven/delivery_queue.py`:
  - Module-level tuneable constants: `DEFAULT_MAX_RETRIES=3`,
    `DEFAULT_INITIAL_DELAY=0.5`, `DEFAULT_BACKOFF_MULTIPLIER=2.0`,
    `DEFAULT_MAX_DELAY=30.0`.
  - `_deliver_with_retry()` uses exponential backoff with jitter; logs ERROR
    after all retries exhausted (SYNC-04-001, SYNC-05-001).
- Added `RejectLogEntryActivity` in `vultron/wire/as2/vocab/activities/sync.py`.
- Added `RejectLogEntryPattern` in `vultron/wire/as2/extractor.py`.
- Added `REJECT_CASE_LOG_ENTRY` to `MessageSemantics` and registered
  `RejectLogEntryReceivedEvent` in `vultron/core/models/events/`.

**Files created**:

- `vultron/core/models/replication_state.py` — `VultronReplicationState`
  persistable model; `id_` auto-computed as `{case_id}/replication/{peer_id}`.
- `vultron/wire/as2/vocab/objects/replication_state.py` — wire-layer vocab
  registration for `VultronReplicationState`.
- `test/core/use_cases/received/test_reject_sync.py` — 15 tests for
  `RejectLogEntryReceivedUseCase` and `replay_missing_entries_trigger`.
- `test/adapters/driven/test_delivery_backoff.py` — 15 tests for
  `DeliveryQueueAdapter` retry/backoff behavior.

**Files modified**:

- `vultron/core/models/events/base.py` — added `ANNOUNCE_CASE_LOG_ENTRY`,
  `REJECT_CASE_LOG_ENTRY`.
- `vultron/core/models/events/sync.py` — added `AnnounceLogEntryReceivedEvent`,
  `RejectLogEntryReceivedEvent` with `last_accepted_hash` fallback to
  `GENESIS_HASH`.
- `vultron/core/models/events/__init__.py` — registered both new event types.
- `vultron/core/use_cases/received/sync.py` — added both use cases plus
  `_find_local_actor_id`, `_update_replication_state`, `_send_rejection`
  helpers.
- `vultron/core/use_cases/triggers/sync.py` — added
  `announce_log_entry_trigger` and `replay_missing_entries_trigger`.
- `vultron/core/use_cases/use_case_map.py` — registered both new use cases.
- `vultron/wire/as2/vocab/activities/sync.py` — added
  `AnnounceLogEntryActivity`, `RejectLogEntryActivity`.
- `vultron/wire/as2/extractor.py` — added both patterns.
- `vultron/adapters/driven/delivery_queue.py` — retry/backoff with exponential
  delay and ERROR-level exhaustion logging.
- `test/core/use_cases/received/test_sync.py` — added hash-mismatch rejection
  tests.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` → 0 errors
- `uv run pyright` → 0 new errors (23 pre-existing in `test_note_trigger.py`
  and `test_reject_sync.py`, matching existing pattern)
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1544 passed, 12 skipped, 5581 subtests passed in 435.02s`
