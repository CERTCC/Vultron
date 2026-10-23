---
title: "D5-6-DUP \u2014 Fix duplicate VulnerabilityReport WARNING (2026-04-07)"
type: implementation
timestamp: '2026-04-07T00:00:00+00:00'
source: D5-6-DUP
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 4782
legacy_heading: "D5-6-DUP \u2014 Fix duplicate VulnerabilityReport WARNING\
  \ (2026-04-07)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-07'
---

## D5-6-DUP — Fix duplicate VulnerabilityReport WARNING (2026-04-07)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:4782`
**Canonical date**: 2026-04-07 (git blame)
**Legacy heading**

```text
D5-6-DUP — Fix duplicate VulnerabilityReport WARNING (2026-04-07)
```

**Legacy heading dates**: 2026-04-07

**Root cause**: The inbox endpoint (`actors.py`) pre-stores any inline nested
object (e.g. the `VulnerabilityReport` inside an `Offer`) before dispatching.
When `SubmitReportReceivedUseCase` (or `CreateReportReceivedUseCase`) then
calls `dl.create()` on the same report, a `ValueError` is raised and was
previously logged at `WARNING`. This is a false-positive — the duplicate is an
expected idempotency condition, not a real error.

**Fix**: Changed the log level from `WARNING` to `DEBUG` in both
`SubmitReportReceivedUseCase` and `CreateReportReceivedUseCase`, with
explanatory comments. This matches the pattern already used for the activity
duplicate handling in `SubmitReportReceivedUseCase` (lines 116-123 before this
change). Added `TestDuplicateReportHandling` class with two tests confirming
no WARNING is emitted when the report has been pre-stored by the inbox
endpoint.

**Files changed**:

- `vultron/core/use_cases/received/report.py`
- `test/core/use_cases/received/test_report.py`
