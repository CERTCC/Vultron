---
source: CONCERN-652
timestamp: '2026-06-04T13:36:25.897305+00:00'
title: triggers/case.py high-churn — test coverage and PR scope
type: learning
---

## Summary

`vultron/core/use_cases/triggers/case.py` has accumulated 31 commits in the
last 90 days. It co-evolves with embargo and participant trigger logic and
is frequently modified as the case-creation and delegation protocols change.

## Category

- [x] Fragile / high-churn area

## Severity

low

## Evidence

- `vultron/core/use_cases/triggers/case.py` (31 churn hits / 90 days; 26
  commits visible at ingest time, 520 lines, 6 trigger use cases)
- Half of the file's use cases (`SvcCreateCase`, `SvcAddObjectToCase`,
  `SvcAddReportToCase`) had no dedicated unit test at ingest time; coverage
  was incidental via `test_trignotify.py` and scenario demos only.

## Impact if Ignored

Case trigger logic changes made without integration test coverage can silently
break the case-creation → actor delegation → announcement pipeline, especially
when a PR bundles case and embargo trigger changes (the common pattern).

## Suggested Action

Narrow PRs with explicit integration tests for each case state transition.
Avoid bundling case and embargo trigger changes in the same PR.

**Resolved**: 2026-06-04 — captured as a durable countermeasure in
`notes/triggers-test-coverage.md` and `AGENTS.md` pitfall index. Two
implementation issues opened: #741 (test backfill for the three
uncovered use cases; independent, ready now) and #742 (split case.py
into a `triggers/case/` subpackage following the BTND-07 pattern;
sequenced after #711 so the split operates on the post-refactor file).

Docs PR: <https://github.com/CERTCC/Vultron/pull/743>. Implementation
tracked in #741 and #742.
