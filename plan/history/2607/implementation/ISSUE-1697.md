---
source: ISSUE-1697
timestamp: '2026-07-27T13:40:17.931481+00:00'
title: Add per-case time range to report header (DRPT-04-006)
type: implementation
---

## Issue #1697 — Implement DRPT-04-006: per-case time range in report header

Added `_case_time_range` helper and emitted `Time range: {first} – {last}` in both markdown and HTML renderers, between the case heading and event table. Omitted when all `received_at` values are None. 11 new tests added covering helper edge cases and both renderer paths. All 4 ACs satisfied.

PR: <https://github.com/CERTCC/Vultron/pull/1704>
