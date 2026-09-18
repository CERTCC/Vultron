---
source: CONCERN-3384
timestamp: '2026-09-18T16:42:41.141319+00:00'
title: demo sync-verification participant waits crash the scenario on timeout
type: learning
---

The `_phase_sync_verification` replica participant waits — routed through the shared `wait_for_participants_on_replicas` helper in `vultron/demo/helpers/polling.py`, called by all seven scenarios — were invoked bare, outside any `demo_check`/`demo_gate` context. On timeout, `wait_for_case_participants` raises `AssertionError`.

That `AssertionError` propagated uncaught out of `_phase_sync_verification` and crashed the whole demo run at the first failure, contradicting the demo failure-accumulation model (DEMOCI-01-003 / DEMOCI-01-004): failures are supposed to accumulate via demo_check/demo_gate/demo_step and surface together at the end via `assert_demo_success()`. A bare raise stops the run before later checks execute, burying any co-occurring failures — the "misleading output" concern the #2852 reporter raised, generalized beyond the fvv timeout that #2852 actually fixed.

Placement of the participant waits *outside* the SYNC-15 gate is intentional and consistent across all siblings — they are independent bounded-timeout checks, not gate-dependent steps. #2852 fixed only the fvv-specific missing late-joiner timeout and deliberately preserved this placement.

**Evidence / precedent**: #1772 / #1802 (Bug A) fixed exactly this crash-vs-accumulate pattern for the bare `wait_for_contiguous_ledger_coverage` calls by wrapping them in `demo_check`; see `test/demo/test_fvv_demo.py::TestCoverageWaitInsideDemoCheck`. The participant waits were never given the same treatment. This is now the second witness of the same failure class, so the constraint was promoted to a spec requirement (DEMOCI-01-011) enforced by an architecture ratchet, rather than left to reviewer vigilance.

**Resolution direction (planned)**: factor the wrap into the shared `wait_for_participants_on_replicas` helper (each per-replica poll wrapped in `demo_check`, lazy-importing from `vultron.demo.utils`, mirroring the existing `drain_phase1_ledger` pattern), so all seven callers inherit it (DRY) and one replica's timeout no longer hides another's.

**Resolved**: 2026-09-18 — implementation tracked in #3406.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3405>.
Spec: `specs/demo-ci.yaml` (DEMOCI-01-011).
Notes: `notes/demo-scenario-authoring.md`.
