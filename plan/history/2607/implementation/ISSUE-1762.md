---
source: ISSUE-1762
timestamp: '2026-07-28T16:25:30.241197+00:00'
title: Replace absolute timestamp with delta-T column
type: implementation
---

## Issue #1762 — Report: implement delta-T Time column (DRPT-04-007)

Replaced the absolute ISO-8601 `Time` column in the demo report case timeline table with a compact `ΔT` column showing elapsed time from the previous row.

Added `_format_delta()` helper, updated both markdown and HTML renderers with `prev_ts` state tracking, and added 13 unit tests plus renderer integration tests.

PR: <https://github.com/CERTCC/Vultron/pull/1764>
