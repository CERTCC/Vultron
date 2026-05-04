---
title: "SYNC-1 \u2014 Local append-only case event log with indexing (2026-04-11)"
type: implementation
timestamp: '2026-04-11T00:00:00+00:00'
source: SYNC-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 5677
legacy_heading: "SYNC-1 \u2014 Local append-only case event log with indexing\
  \ (2026-04-11)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-11'
---

## SYNC-1 — Local append-only case event log with indexing (2026-04-11)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:5677`
**Canonical date**: 2026-04-11 (git blame)
**Legacy heading**

```text
SYNC-1 — Local append-only case event log with indexing (2026-04-11)
```

**Legacy heading dates**: 2026-04-11

**Task**: Implement the core domain models for the canonical case event log
foundation required by `specs/sync-log-replication.yaml` SYNC-01 and
`specs/case-log-processing.yaml` CLP-01 through CLP-05. Also add the
leadership guard port to `BTBridge` per SYNC-09-003.

**Files created**:

- `vultron/core/models/case_log.py` — `CaseLogEntry`, `CaseEventLog`,
  `ReplicationState`, `GENESIS_HASH`, and canonical-serialisation helpers.
- `test/core/models/test_case_log.py` — 52 unit tests covering all new
  models and the BTBridge leadership guard.

**Files modified**:

- `vultron/core/behaviors/bridge.py` — Added `is_leader: Callable[[], bool]`
  port to `BTBridge.__init__` (default: `_default_is_leader`, always `True`).
  `execute_with_setup` now checks `is_leader()` and returns a FAILURE result
  immediately when the check fails (SYNC-09-003).

**What was implemented**:

1. **`CaseLogEntry`** (Pydantic `BaseModel`) — single canonical log entry:
   - `log_index` (int) — monotonically increasing, scoped to case
     (CLP-02-006, SYNC-01-002)
   - `disposition` (`"recorded"` | `"rejected"`) (CLP-02-004)
   - `term` (optional int) — Raft term, `None` for single-node (CLP-02-007)
   - `payload_snapshot` (dict) — normalized activity snapshot for replay
     (CLP-02-003, SYNC-08-002)
   - `prev_log_hash` (str) — predecessor entry hash; `GENESIS_HASH` for
     first entry (SYNC-01-003)
   - `entry_hash` (str) — SHA-256 of canonical content (auto-computed via
     `model_validator`; excludes itself from hashed fields) (SYNC-01-003)
   - `reason_code` / `reason_detail` — for rejected entries (CLP-02-005)
   - `verify_hash()` method for tamper detection
   - Canonical serialisation uses RFC 8785 JCS-compatible JSON
     (`sort_keys=True`, compact separators) (SYNC-01-005)

2. **`CaseEventLog`** — append-only hash-chained log per case (SYNC-01-001):
   - `append(object_id, event_type, disposition, ...)` — assigns
     `log_index`, chains `prev_log_hash` from `tail_hash`, computes
     `entry_hash` automatically
   - `entries` property — immutable tuple of all entries (both dispositions)
   - `recorded_entries` property — filtered projection of `"recorded"` entries
     only (CLP-04-001, CLP-04-003)
   - `tail_hash` property — hash of last recorded entry or `GENESIS_HASH`
   - `verify_chain()` — validates hash-chain and index sequence integrity
   - Rejected entries require `reason_code` (raises `ValueError` if absent)

3. **`ReplicationState`** (Pydantic `BaseModel`) — per-peer replication state
   tracking (SYNC-04-001, SYNC-04-002):
   - `peer_id` — full URI of participant actor
   - `last_acknowledged_hash` — defaults to `GENESIS_HASH` for new peers

4. **`BTBridge` leadership guard** (SYNC-09-003):
   - New `is_leader: Callable[[], bool]` constructor parameter
   - Default: `_default_is_leader` always returns `True` (single-node)
   - `execute_with_setup` returns FAILURE immediately when `is_leader()`
     is `False`, with a descriptive log warning

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1499 passed, 10 skipped, 5581 subtests passed in 80.97s`
