---
source: ISSUE-741
timestamp: '2026-06-05T20:27:56.154648+00:00'
title: Backfill unit tests for trigger use cases
type: implementation
---

## Issue #741 — Backfill dedicated unit tests for SvcCreateCase, SvcAddObjectToCase, and SvcAddReportToCase trigger use cases

Added three dedicated unit-test files to close regression coverage gaps in trigger use cases:

- **test/core/use_cases/triggers/test_svc_create_case.py** (6 tests): Exercises SvcCreateCaseUseCase including happy paths (case creation with/without linked report), error conditions (missing actor, report not found, report wrong type), and outbox delivery verification.

- **test/core/use_cases/triggers/test_svc_add_object_to_case.py** (6 tests): Exercises SvcAddObjectToCaseUseCase including happy path, error conditions (missing actor/case/object), multiple object additions, and delivery queue verification.

- **test/core/use_cases/triggers/test_svc_add_report_to_case.py** (7 tests): Exercises SvcAddReportToCaseUseCase including validation, error conditions, delegation to SvcAddObjectToCaseUseCase, and multiple report additions.

All 27 new tests pass. Full test suite: 3024 passed, 12 skipped. Per
notes/triggers-test-coverage.md, every trigger use case now has dedicated
regression tests that exercise execute() against a real in-memory DataLayer
and assert state mutation, outbox effects, and documented failure modes.

**PR**: [#816](https://github.com/CERTCC/Vultron/pull/816)
