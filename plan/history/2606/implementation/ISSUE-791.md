---
source: ISSUE-791
timestamp: '2026-06-16T16:16:40.196375+00:00'
title: 'Add catch-up gate: is_ledger_fresh_for_case + CheckLedgerFreshnessNode'
type: implementation
---

## Issue #791 — Require case-ledger catch-up before new actor actions

Implemented the case-ledger catch-up gate required by SYNC-10-001 through
SYNC-10-005. An actor with a non-contiguous local ledger (e.g. after restart
or recovery) is blocked from taking new protocol-significant case actions
until its acknowledged prefix forms a contiguous hash-chained sequence from
genesis through its current tip. An empty local ledger is trivially fresh
per SYNC-10-005.

**Changes:**

- `vultron/core/sync_helpers.py`: Added `is_ledger_fresh_for_case(case_id, dl)`
  — verifies entries form an unbroken hash chain from `log_index=0`
  (`prev_log_hash==GENESIS_HASH`) through the actor's highest stored entry.
  Returns `(True, '')` when fresh; `(False, reason)` on any gap or hash
  mismatch.
- `vultron/core/behaviors/sync/nodes/conditions.py`: Added
  `CheckLedgerFreshnessNode` — BT condition that gates on freshness, emits
  WARNING with staleness reason when blocked (SYNC-10-002), and returns
  FAILURE to block protocol-significant actions (SYNC-10-001). Accepts
  `case_id` at construction or reads it from the blackboard key `'case_id'`.
- `vultron/core/behaviors/sync/nodes/__init__.py`: Re-exported
  `CheckLedgerFreshnessNode`.
- 19 new tests (10 in `test/core/test_sync_helpers.py`, 9 in
  `test/core/behaviors/sync/nodes/test_conditions.py`) covering empty
  ledger, contiguous chains, index gaps, hash mismatches, WARNING emission,
  and blackboard case_id resolution.

All 3410 unit tests pass. Black, flake8, mypy, pyright clean.

PR: [#1000](https://github.com/CERTCC/Vultron/pull/1000)
