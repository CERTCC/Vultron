---
source: CONCERN-3906
timestamp: '2026-09-30T18:41:30.105845+00:00'
title: drain_phase1_ledger keeps a private copy of the replica coverage loop outside
  sync.py
type: learning
---

## Summary

`drain_phase1_ledger` in `vultron/demo/helpers/polling.py` is a third copy of the read-authority-tail-then-poll-each-replica loop that #3846 consolidated into `wait_for_replica_ledger_coverage` in `vultron/demo/helpers/sync.py` (DEMOMA-23-005). Three scenarios (fcvcv, fvcv-extension, fccv-extension) call it as the Phase 1 drain before Phase 2.

## Surface symptom vs. underlying problem

**Surface**: a duplicated ~20-line loop in a helper module — a DRY smell, not a bug.

**Underlying**: DEMOMA-23-005 says *every* wait for a set of replicas to reach contiguous coverage of an authority's tail MUST go through the shared helper in `sync.py`. `drain_phase1_ledger` is such a wait that lives in `polling.py` with its own fixed 30 s budget and its own `demo_gate` label, so the next budget or gate fix lands in one loop and misses the other — the exact drift #3042 described. It was left in place in #3846 because the architecture ratchet `test/architecture/test_demo_scenario_waits_in_demo_context.py` classifies a polling helper as "wrapping" only when its body contains a literal `with demo_gate/demo_check(...)` around every raising call; `wait_for_replica_ledger_coverage` selects its context through a variable (`context = demo_gate if causal else demo_check`), so a `drain_phase1_ledger` that merely delegated to it would be classified as raising and the three bare scenario calls would be flagged.

## Category / severity

Design debt, low severity: no incorrect behaviour today; the risk is divergence on the next timeout or gate change.

## Evidence

- `vultron/demo/helpers/polling.py::drain_phase1_ledger` (reads the tail via `_get_log_entries_for_case`, loops `wait_for_contiguous_ledger_coverage` inside `demo_gate`).
- `vultron/demo/helpers/sync.py::wait_for_replica_ledger_coverage` (#3846, PR #3905).
- `test/architecture/test_demo_scenario_waits_in_demo_context.py::_classify_polling_helpers`.

## Impact if ignored

A future budget change (for example to `LEDGER_COVERAGE_TIMEOUT`) or a change to the per-replica gate label reaches the sync-verification and closure waits but not the Phase 1 drain.

## Suggested action

Either (a) teach the ratchet's classifier that a call into a known wrapping helper in `sync.py` is not a raising call — for example by classifying helpers across both `polling.py` and `sync.py` and treating a context-manager *variable* bound to one of the demo contexts as a demo context — and then make `drain_phase1_ledger` a thin call to `wait_for_replica_ledger_coverage(..., phase_label="Phase 1 drain before Phase 2")`; or (b) delete `drain_phase1_ledger` and have the three scenarios call the shared helper directly (its bare-call safety is then asserted by `test/demo/test_sync_phase_helpers.py`, not by the classifier). Extend the DEMOMA-23-006 ratchet to forbid `drain_phase1_ledger` once it is gone.

Governing specs: DEMOMA-23-005, DEMOMA-17-001, DEMOCI-01-011

**Resolved**: 2026-09-30 — implementation tracked in #3956, #3957.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3955>.
Spec: `specs/multi-actor-demo.yaml` (DEMOMA-23-006 widened to every module under
`vultron/demo/` except `helpers/sync.py`).

Decision: option (b) — delete `drain_phase1_ledger` and call
`wait_for_replica_ledger_coverage` directly. The classifier change in option (a)
is not needed for (b), because `sync.py` helpers are never classified. That blind
spot is tracked separately in #3957.
