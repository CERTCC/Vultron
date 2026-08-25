---
source: ISSUE-1820
timestamp: '2026-07-31T15:05:44.194173+00:00'
title: add concurrent-isolation smoke test for slimmed receive_report_case_tree
type: implementation
---

## Issue #1820 — test: add concurrent-isolation smoke test for slimmed receive_report_case_tree

Added `TestConcurrentExecution` class to `test/core/behaviors/case/test_receive_report_case_tree.py` covering BTND-03-004 (blackboard isolation for concurrent BT executions).

Two test methods verify the ADR-0041 slimmed tree under concurrency:

- `test_two_threads_both_succeed`: both threads return `Status.SUCCESS` under `_BT_GLOBAL_LOCK` serialisation
- `test_two_threads_produce_distinct_links`: each thread produces a distinct `VultronReportCaseLink` record

Code-review findings fixed before PR: `activity=None` replaced with per-thread `offer` param, `is_alive()` deadlock detection added after each `join()`, `threading.Lock` guards shared `errors` list.

PR: <https://github.com/CERTCC/Vultron/pull/1860>
