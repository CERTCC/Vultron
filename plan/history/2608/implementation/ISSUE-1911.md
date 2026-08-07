---
source: ISSUE-1911
timestamp: '2026-08-07T20:43:16.476184+00:00'
title: 'fix(demo-ci): raise coverage-wait timeout to 30s to eliminate fv flakiness'
type: implementation
---

Issue #1911: fv Demo Integration CI intermittently failed with
DemoFailureError: 2 demo failure(s). Both failures cascaded from a single root
cause: wait_for_contiguous_ledger_coverage defaulting to 15s in
_phase_sync_verification — under CI scheduling load, the inter-container
Announce(CaseLedgerEntry) fan-out did not complete in time. When that timed out,
the immediately following verify_finder_replica_state found an empty replica and
also failed, producing exactly 2 failures.

Fix: raised the default timeout from 15s to 30s in
vultron/demo/helpers/polling.py, consistent with wait_for_event_type_in_ledger's
20s default. This affects all 9 scenario call sites uniformly.

Regression test added to test/demo/test_fvv_demo.py
(TestWaitForContiguousLedgerCoverage::test_default_timeout_is_sufficient_for_ci_load)
asserting the default is >= 30s.

PR: <https://github.com/CERTCC/Vultron/pull/2113>
