---
title: "PRIORITY-30 partial \u2014 P30-1 through P30-3"
type: implementation
timestamp: '2026-03-09T00:00:00+00:00'
source: PRIORITY-30
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 302
legacy_heading: "Phase PRIORITY-30 partial \u2014 P30-1 through P30-3 (COMPLETE\
  \ 2026-03-06)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-06'
---

## PRIORITY-30 partial — P30-1 through P30-3

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:302`
**Canonical date**: 2026-03-09 (git blame)
**Legacy heading**

```text
Phase PRIORITY-30 partial — P30-1 through P30-3 (COMPLETE 2026-03-06)
```

**Legacy heading dates**: 2026-03-06

- **P30-1**: `vultron/api/v2/routers/triggers.py` created; `validate-report`
  endpoint with `ValidateReportRequest` model (extra="ignore"); structured 404
  helpers; outbox-diff strategy to retrieve resulting activity; registered in
  `v2_router.py`; 9 tests in `test/api/v2/routers/test_triggers.py`. 702 tests
  passing at completion.
- **P30-2**: `invalidate-report` and `reject-report` endpoints added; procedural
  implementation emitting `RmInvalidateReport` (TentativeReject) and
  `RmCloseReport` (Reject) respectively; empty `note` on `reject-report` logs
  WARNING per TB-03-004; 17 new tests; 719 tests passing.
- **P30-3**: `engage-case` and `defer-case` endpoints added; procedural
  implementation emitting `RmEngageCase` (Join) and `RmDeferCase` (Ignore);
  `CaseTriggerRequest` model; `_resolve_case` and `_update_participant_rm_state`
  helpers; 17 new tests; 736 tests passing.
