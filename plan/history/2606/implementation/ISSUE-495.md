---
source: ISSUE-495
timestamp: '2026-06-22T17:21:19.408335+00:00'
title: Split test_report.py into 4 focused files
type: implementation
---

## Issue #495 — Split test_report.py (received) by use-case type

Split the 1,154-line `test/core/use_cases/received/test_report.py` (10 classes,
33 tests) into 4 focused files grouped by use-case type. The shared
`_close_sqlite_datalayers` autouse fixture was promoted to `conftest.py`.

**New files:**

- `test_create_report_received.py` — CreateReport: creation, no-standalone-status,
  duplicate handling (3 classes, 7 tests, 210 lines)
- `test_submit_report_received.py` — SubmitReport: log messages, case creation,
  offer addressing (3 classes, 11 tests, 306 lines)
- `test_report_case_level.py` — InvalidateReport, CloseReport, delegation to case
  use cases (2 classes, 8 tests, 269 lines)
- `test_ack_validate_report_received.py` — AckReport, ValidateReport, full-flow
  integration (3 classes, 10 tests, 383 lines)

All 36 tests pass. Black, flake8, mypy, pyright clean.

PR: <https://github.com/CERTCC/Vultron/pull/1096>
