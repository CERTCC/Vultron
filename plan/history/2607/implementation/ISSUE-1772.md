---
source: ISSUE-1772
timestamp: '2026-07-29T18:47:30.261290+00:00'
title: 'fix flaky invariant harness: wrap coverage waits in demo_check; add close_case
  anchor'
type: implementation
---

Issue #1772 (primary) + #1802 (downstream crash symptom).

Symptoms: Demo scenario runs produced either (A) exit code 1 with no JSONL artifact, or (B) JSONL artifact with a gapped ledger that the invariant harness then rejected.

Root cause A (#1802): All wait_for_contiguous_ledger_coverage calls in _phase_sync_verification and_phase_case_closure were bare (not in demo_check). A polling timeout raised an uncaught AssertionError → exit 1 → no artifact.

Root cause B (#1772): The authoritative-actor tail index was read immediately after wait_for_all_participants_rm_closed. The close_case ledger entry is committed asynchronously by EmitCloseCaseNode after the last RM.CLOSED (a BackgroundTasks dispatch). Reading the tail too early snapshots a stale tail that excludes close_case, so replica coverage succeeds against the wrong tail, the JSONL is gapped, and the invariant harness fails.

Fix: (1) Wrap all coverage waits in demo_check so timeouts accumulate to_demo_failures rather than crashing. (2) Add wait_for_event_type_in_ledger(close_case) before the tail read in each close phase so close_case is always included in the tail before replica coverage begins.

New helper: wait_for_event_type_in_ledger in vultron/demo/helpers/polling.py.

Regression tests in test/demo/test_fvv_demo.py: TestCoverageWaitInsideDemoCheck (Bug A) + TestWaitForEventTypeInLedger x4 (Bug B).

All 7 scenario files patched: fv, fvv, fcv, fvcv-extension, fvcv-handoff, fccv-extension, fccv-handoff.

PR: <https://github.com/CERTCC/Vultron/pull/1819>
