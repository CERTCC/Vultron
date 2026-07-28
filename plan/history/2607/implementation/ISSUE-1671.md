---
source: ISSUE-1671
timestamp: '2026-07-27T15:06:14.197630+00:00'
title: Wire EvaluateCasePriority into PrioritizationCallOutBundle
type: implementation
---

## Issue #1671 — Wire EvaluateCasePriority into PrioritizationCallOutBundle

Completed wiring of `EvaluateCasePriority` as a proper injectable call-out point
in `PrioritizationCallOutBundle` per BT-18-004 and BT-23-003.

Changes:

- Added `EvaluateCasePriority` fuzzer stub to `prioritize.py` (SSVC seam, PROTO-05-001)
- Added `evaluate_priority_factory` field to `PrioritizationCallOutBundle` with
  `AlwaysSucceed` deterministic default and `_stochastic_evaluate_priority` in stochastic singleton
- Replaced hardcoded `EvaluateCasePriority(case_id=case_id)` in `create_prioritize_subtree`
  with `bundle.evaluate_priority_factory("EvaluateCasePriority")`
- Added factory injection test (AC-4) and updated defer test from monkeypatch to factory injection

PR: <https://github.com/CERTCC/Vultron/pull/1710>
