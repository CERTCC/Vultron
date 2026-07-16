---
source: ISSUE-1377
timestamp: '2026-07-14T18:54:43.276424+00:00'
title: fix fail-fast at silent-failure sites in core domain helpers
type: implementation
---

## Issue #1377 — fix: fail-fast at silent-failure sites in core domain helpers

Applied fail-fast behaviour at all 5 named silent-failure sites from CONCERN-1360.

**Changes made:**

- `vultron/errors.py`: added `UnroutableActivityError` with `activity_id` and `reason` fields
- `vultron/core/behaviors/case/nodes/lifecycle.py`: `CommitCaseLedgerEntryNode` returns FAILURE (not SUCCESS) when `case_id` unresolvable
- `vultron/core/behaviors/case/nodes/communication.py`: `_read_case_obj()` sets `feedback_message` + logs ERROR on KeyError; `update()` returns FAILURE when `case_obj` is None
- `vultron/core/dispatcher.py`: `_extract_case_id()` raises `UnroutableActivityError` instead of returning None; `_handle()` catches and drops unroutable events (prevents infinite retry loop)
- `test/core/behaviors/case/nodes/test_lifecycle.py`: updated SUCCESS→FAILURE assertion
- `test/core/test_fail_fast_silent_sites.py`: 11 new dedicated tests

**Code review finding fixed:** `UnroutableActivityError` caught in `_handle` before reaching `_process_inbox_item`'s re-queue loop.

PR: <https://github.com/CERTCC/Vultron/pull/1422>
