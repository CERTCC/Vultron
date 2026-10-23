---
source: ISSUE-903
timestamp: '2026-06-11T20:29:50.792893+00:00'
title: Duplicate-delivery idempotency coverage
type: implementation
---

## Issue #903 — SYNC Integration: duplicate-delivery idempotency for CaseLogEntry

Added a new integration test in `test/demo/test_sync_log_replication.py` that delivers the same `Announce(CaseLogEntry)` twice through isolated FastAPI apps and the shared `_TestASGIRouter`.

The test now proves the idempotency guard by asserting the peer DataLayer saves the `CaseLogEntry` exactly once, instead of relying only on the final replica row count.

PR: [#919](https://github.com/CERTCC/Vultron/pull/919)
