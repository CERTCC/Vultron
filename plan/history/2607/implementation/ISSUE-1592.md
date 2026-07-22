---
source: ISSUE-1592
timestamp: '2026-07-22T16:42:33.269093+00:00'
title: Modularize case-ledger invariant harness
type: implementation
---

## Issue #1592 — refactor: modularize case-ledger invariant harness for per-scenario test files

Extracted `test/ci/invariants/common.py` shared library with 15 composable check functions. Refactored monolithic 864-line test file into `test_fv_invariants.py`. Added FVV and FVCV-extension stubs (`test_fvv_invariants.py`, `test_fvcv_extension_invariants.py`). Updated README with scenario table and contributor guide. All 5304 tests pass; 106 skip cleanly when devlogs absent. Follow-up issue #1600 tracks finder late-joiner backfill for FVV/FVCV-extension once demos exist. PR: <https://github.com/CERTCC/Vultron/pull/1602>
