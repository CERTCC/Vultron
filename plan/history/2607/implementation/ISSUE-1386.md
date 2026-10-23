---
source: ISSUE-1386
timestamp: '2026-07-15T14:58:12.032606+00:00'
title: Add execute()-path tests for SvcValidateReportUseCase and SvcSubmitReportUseCase
type: implementation
---

## Issue #1386 — test: add dedicated execute()-path tests for SvcValidateReportUseCase and SvcSubmitReportUseCase

Added `test/core/use_cases/triggers/test_report_triggers.py` with 16 unit tests (9 for SvcValidateReportUseCase, 7 for SvcSubmitReportUseCase) covering RM state mutations, outbox effects (PCR-08-001 routing), and documented failure modes. All tests run against a real in-memory SqliteDataLayer. PR: <https://github.com/CERTCC/Vultron/pull/1437>
