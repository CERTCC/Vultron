---
title: "TECHDEBT-33 \u2014 Split test_handlers.py"
type: implementation
timestamp: '2026-03-23T00:00:00+00:00'
source: TECHDEBT-33
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2608
legacy_heading: "TECHDEBT-33 \u2014 Split test_handlers.py (COMPLETE 2026-03-23)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-23'
---

## TECHDEBT-33 — Split test_handlers.py

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2608`
**Canonical date**: 2026-03-23 (git blame)
**Legacy heading**

```text
TECHDEBT-33 — Split test_handlers.py (COMPLETE 2026-03-23)
```

**Legacy heading dates**: 2026-03-23

Split the 2227-line monolithic `test/api/v2/backend/test_handlers.py` into
per-module test files under `test/core/use_cases/`, mirroring the source
layout. Four test classes had already been migrated in earlier runs (actor,
case_participant, basic report/use-case execution); this run completed the
remaining migrations:

- `test_embargo_use_cases.py` — `TestEmbargoUseCases` (11 tests)
- `test_note_use_cases.py` — `TestNoteUseCases` (6 tests)
- `test_status_use_cases.py` — `TestStatusUseCases` (7 tests)
- `test_case_use_cases.py` — `TestCaseUseCases` (6 tests)
- `test_report_use_cases.py` — `TestReportReceiptRM` (3 tests, appended)
- Deleted `test/api/v2/backend/test_handlers.py`

976 tests pass at completion (was 913; the increase reflects newly visible
migrated tests that had previously been duplicated in the old file).

### Commits

- 8f34be9: "test: TECHDEBT-33 — split test_handlers.py into per-module use-case test files"
