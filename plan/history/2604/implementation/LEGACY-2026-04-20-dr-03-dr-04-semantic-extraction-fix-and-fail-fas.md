---
title: 'DR-03 / DR-04: Semantic extraction fix and fail-fast validation'
type: implementation
timestamp: '2026-04-20T00:00:00+00:00'
source: LEGACY-2026-04-20-dr-03-dr-04-semantic-extraction-fix-and-fail-fas
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7035
legacy_heading: "2026-04-20 \u2014 DR-03 / DR-04: Semantic extraction fix\
  \ and fail-fast validation"
date_source: git-blame
legacy_heading_dates:
- '2026-04-20'
---

## DR-03 / DR-04: Semantic extraction fix and fail-fast validation

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7035`
**Canonical date**: 2026-04-20 (git blame)
**Legacy heading**

```text
2026-04-20 — DR-03 / DR-04: Semantic extraction fix and fail-fast validation
```

**Legacy heading dates**: 2026-04-20

**Tasks completed:** DR-03 (High), DR-04 (High)

**Summary:**

Fixed two bugs from the 2026-04-20 demo review that caused inbox crash-loops
when unresolved ActivityStreams references (bare string IDs) were received.

### DR-03 — _match_field() ordering fix in ActivityPattern.match()

**Root cause:** `_match_field()` in `ActivityPattern.match()` checked
`isinstance(activity_field, str)` (conservative allow) BEFORE checking
`isinstance(pattern_field, ActivityPattern)` (nested pattern check). This
caused `Accept("bare-string-id")` to satisfy nested-activity pattern
constraints (e.g., `ReportSubmissionPattern`), causing `Accept(bare_string)`
to be classified as `VALIDATE_REPORT`, triggering a downstream `ValueError`
and inbox retry loop.

**Fix:** Moved the `isinstance(pattern_field, ActivityPattern)` check BEFORE
the string passthrough in `_match_field()`. Bare string `object_` values now
return `False` when the pattern requires a nested typed activity (instead of
`True`), causing those activities to dispatch as `UNKNOWN` (which just logs
a warning and returns cleanly).

**Files changed:**

- `vultron/wire/as2/extractor.py` — reordered `_match_field()` checks
- `test/test_semantic_activity_patterns.py` — new test:
  `test_accept_with_bare_string_object_returns_unknown`

### DR-04 — Fail-fast validation for ValidateReportReceivedEvent

Added `@model_validator(mode='after')` to `ValidateReportReceivedEvent` to
raise `ValueError` at construction time when `offer_id` or `report_id` is
`None`. Previously the check was only inside `execute()` as a bare
`ValueError`. Updated the residual check in
`ValidateReportReceivedUseCase.execute()` to raise `VultronValidationError`
(domain error) instead of bare `ValueError`.

**Files changed:**

- `vultron/core/models/events/report.py` — added `model_validator` to
  `ValidateReportReceivedEvent`
- `vultron/core/use_cases/received/report.py` — imported and used
  `VultronValidationError` instead of bare `ValueError`

### DR-07 — AnnounceLogEntryActivity immediate fix

Already complete in a prior commit (`AnnounceLogEntryPattern` already has
`object_=VOtype.CASE_LOG_ENTRY`). The `InviteActorToCasePattern` sub-issue
(add `object_=AOtype.ACTOR`) was attempted but reverted: `AOtype.ACTOR`
only matches `type_="Actor"` (the base AS2 Actor class), while real invite
activities use actor subtypes (`Person`, `Organization`, `Service`) which
have `type_!="Actor"`. The pattern would need subtype-aware matching to
implement correctly. Noted in IMPLEMENTATION_NOTES.md for DR-07 audit.

**Test Result:**

1674 passed, 12 skipped, 182 deselected, 5581 subtests passed
