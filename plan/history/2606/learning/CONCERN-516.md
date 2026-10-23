---
source: CONCERN-516
timestamp: '2026-06-03T17:26:02.923544+00:00'
title: embargo.py high-churn/mixed-responsibility concern
type: learning
---

## Summary

`vultron/core/use_cases/triggers/embargo.py` has grown to 902 lines and
accumulated 38 commits in the last 90 days, making it one of the highest-churn
source files. It encodes complex embargo state-transition logic inline in
trigger use-case methods.

## Category

- [x] Fragile / high-churn area

## Severity

medium

## Evidence

- `vultron/core/use_cases/triggers/embargo.py` (902 lines, 38 churn hits / 90 days)
- Scan output: top source-file churn ranking

## Impact if Ignored

State-machine logic embedded in trigger methods is hard to audit against the
protocol spec and harder to test in isolation. Regressions in embargo
state transitions are difficult to catch without comprehensive integration
tests.

## Suggested Action

Write narrow PRs with explicit test coverage for each embargo state
transition. Consider migrating inline state logic to BT nodes where the
protocol requires conditional branching.

**Resolved**: 2026-06-03 — structural concern absorbed by #538
(EmbargoLifecycle service RFC). Concern is now blocked-by #538; post-#538
cleanup tracked in #696. Documentation added in `notes/embargo-lifecycle.md`
capturing the inline-EMAdapter anti-pattern and target architecture.
Docs PR: <https://github.com/CERTCC/Vultron/pull/697>.
Implementation tracked in #696 (blocked by #538).
