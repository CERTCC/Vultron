---
source: CONCERN-2701
timestamp: '2026-09-03T13:41:01.089404+00:00'
title: 'ValidateCaseStatusTransitionNode: stale concern resolved by PR #2805 (per-dimension
  validation superseded it)'
type: learning
---

## Summary

`case_status.py:108` defined `ValidateCaseStatusTransitionNode` but it was no longer
wired into any behavior tree in the codebase. At runtime, CS state transition
validation was silently skipped for every case status update.

## Location

`vultron/core/behaviors/status/nodes/case_status.py` line 108

## Observed during

Code review on PR #2683. Pre-existing, not in that PR's diff.

## Investigation

PR #2805 ("refactor(status): remove superseded all-or-nothing CS/RM validator
nodes", merged 2026-08-28, commit `15d8fe6ce`) resolved the underlying issue by
removing `ValidateCaseStatusTransitionNode` entirely. The node was superseded by
per-dimension filter nodes introduced in ISSUE-2256 (ADR-0061, RSH-05):

- `FinalizeCsFilterNode`
- `CheckCsEphemeralStateNode`
- `CheckCsHistoryPrefixNode`

CS transition validation is NOT silently skipped — the per-dimension nodes provide
equivalent (and better) coverage. The `REJECTION_VALIDATORS` architectural test guard
was also cleaned up by PR #2805.

Near-duplicate concern #2740 was explicitly closed by PR #2805. Concern #2701 was
inadvertently omitted from the `Closes #N` list in that PR.

**Resolved**: 2026-09-03 — concern stale; underlying issue fixed by PR #2805 which
closed near-duplicate #2740. No implementation issues created.
