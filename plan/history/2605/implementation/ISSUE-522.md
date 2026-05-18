---
source: ISSUE-522
timestamp: '2026-05-18T15:57:36.396694+00:00'
title: 'PCR-07-006: Bootstrap sequence integration tests'
type: implementation
---

## Issue #522 — PCR-07-006: Integration test — full bootstrap sequence

Added `test/demo/test_pcr_bootstrap.py` with three `@pytest.mark.integration`
tests verifying the full case-replica bootstrap sequence (Create → Announce →
replica → routing). Tests use real SQLite DataLayer instances and the HTTP
inbox dispatch path without mocking use cases. PR: #544.
