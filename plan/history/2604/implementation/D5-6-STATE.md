---
title: 'D5-6-STATE: Fix Finder RM State Initialization in SubmitReportReceivedUseCase'
type: implementation
timestamp: '2026-04-06T00:00:00+00:00'
source: D5-6-STATE
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 4489
legacy_heading: 'D5-6-STATE: Fix Finder RM State Initialization in SubmitReportReceivedUseCase'
date_source: git-blame
---

## D5-6-STATE: Fix Finder RM State Initialization in SubmitReportReceivedUseCase

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:4489`
**Canonical date**: 2026-04-06 (git blame)
**Legacy heading**

```text
D5-6-STATE: Fix Finder RM State Initialization in SubmitReportReceivedUseCase
```

**Task**: D5-6-STATE (PRIORITY-310 demo feedback)
**Addresses**: D5-6c from `notes/two-actor-feedback.md` — ambiguous RM state
log messages; finder participant status incorrectly initialized to `RM.RECEIVED`

### Problem

When a vendor's inbox received a submitted (`Offer`) report from a finder,
`SubmitReportReceivedUseCase` created the finder's `VultronParticipantStatus`
with `rm_state=RM.RECEIVED`. This was semantically wrong: `RM.RECEIVED` is
the **vendor's** state after receiving a new report. A finder who submits a
report has already progressed through their own RM cycle to `RM.ACCEPTED`.
The log message `"RM START → RECEIVED for report '...' (actor '...')"` was
also ambiguous about which participant's state was being described.

### Changes

1. **`vultron/core/use_cases/received/report.py`**: In
   `SubmitReportReceivedUseCase.execute()`, changed finder participant status
   initial `rm_state` from `RM.RECEIVED` to `RM.ACCEPTED`. Updated
   `_idempotent_create` label to `"ParticipantStatus (report-phase RM.ACCEPTED)
   for finder"`. Updated log to `"Finder RM: START → ACCEPTED for report '%s'
   (finder: '%s')"`.

2. **`test/core/use_cases/received/test_report.py`**: Updated existing test
   to check `RM.ACCEPTED`; added negative test, idempotency test, and log
   message verification test class `TestSubmitReportLogMessages`.

### Validation

`uv run pytest --tb=short 2>&1 | tail -5` → 1211 passed, 5581 subtests;
black/flake8/mypy/pyright all clean.
