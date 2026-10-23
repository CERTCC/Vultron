---
title: "IDEA-260408-01-5 and IDEA-260408-01-6 \u2014 Dereference Pattern +\
  \ Remove Standalone VultronParticipantStatus"
type: implementation
timestamp: '2026-04-09T00:00:00+00:00'
source: LEGACY-2026-04-09-idea-260408-01-5-and-idea-260408-01-6-dereferenc
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 5234
legacy_heading: "IDEA-260408-01-5 and IDEA-260408-01-6 \u2014 Dereference\
  \ Pattern + Remove Standalone VultronParticipantStatus"
date_source: git-blame
---

## IDEA-260408-01-5 and IDEA-260408-01-6 — Dereference Pattern + Remove Standalone VultronParticipantStatus

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:5234`
**Canonical date**: 2026-04-09 (git blame)
**Legacy heading**

```text
IDEA-260408-01-5 and IDEA-260408-01-6 — Dereference Pattern + Remove Standalone VultronParticipantStatus
```

**Completed**: 2026-04-08
**Commit**: `d5 f2ff3ebe`

### Summary

Implemented the dereference pattern for report-centric use cases and removed
standalone `VultronParticipantStatus` creation from `CreateReport` and
`AckReport` use cases.

### Changes

**`vultron/core/use_cases/received/case.py`** — added three internal case-level
helpers not in `USE_CASE_MAP`:

- `InvalidateCaseUseCase(dl, case_id, actor_id)` — transitions participant to
  `RM.INVALID`
- `CloseCaseUseCase(dl, case_id, actor_id)` — transitions participant to
  `RM.CLOSED`
- `ValidateCaseUseCase(dl, case_id, actor_id)` — runs `validate_report_tree` BT

**`vultron/core/use_cases/received/report.py`** — updated three use cases:

- `InvalidateReportReceivedUseCase`: dereferences `report_id → case_id` via
  `find_case_by_report_id`, then delegates to `InvalidateCaseUseCase`
- `CloseReportReceivedUseCase`: same pattern, delegates to `CloseCaseUseCase`
- `ValidateReportReceivedUseCase`: same pattern, delegates to `ValidateCaseUseCase`
- `CreateReportReceivedUseCase`: removed standalone `VultronParticipantStatus`
  creation
- `AckReportReceivedUseCase`: removed standalone `VultronParticipantStatus`
  creation

**`test/core/use_cases/received/test_report.py`** — updated tests:

- Replaced `TestReportReceiptPersistsParticipantStatus` with
  `TestCreateReportNoStandaloneParticipantStatus`
- Added `TestCaseLevelUseCases`, `TestDereferencePatternInReportUseCases`,
  `TestAckReportNoStandaloneStatus`
- Used `cast()` to narrow `dl.read()` return types for pyright
- Fixed close tests: use `RM.INVALID` as initial state (`RECEIVED → CLOSED`
  is not a valid RM transition; valid sources are `INVALID`, `ACCEPTED`,
  `DEFERRED`)

### Validation

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` / `uv run pyright` → 0 errors
- `uv run pytest --tb=short 2>&1 | tail -5` → `1299 passed, 5581 subtests passed in 42.49s`
