---
source: ISSUE-1858
timestamp: '2026-08-05T14:51:26.881653+00:00'
title: Leave-case round-trip, announce-tree, and demo endpoint tests
type: implementation
---

## Issue #1858 — test(#1858): add leave-case round-trip, announce-tree, and demo endpoint tests

Added 11 new tests across three files to complete coverage for the SvcLeaveCaseUseCase / Leave(VulnerabilityCase) closure path. The core implementation was already fully present at HEAD via PRs #1901, #1965, and #1966.

New files/additions:

- test/core/use_cases/test_leave_case_round_trip.py (new): AC-5 end-to-end round-trip across two SqliteDataLayer replicas
- test/core/behaviors/sync/test_announce_tree.py: TestAnnounceLogEntryAppliesCloseCase + failure-blocks-persist test
- test/adapters/driving/fastapi/routers/test_demo_triggers.py: TestDemoCloseCase (4 tests)

PR: <https://github.com/CERTCC/Vultron/pull/1909>
