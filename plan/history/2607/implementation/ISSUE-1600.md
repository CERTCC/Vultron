---
source: ISSUE-1600
timestamp: '2026-07-23T19:08:18.236034+00:00'
title: Add finder late-joiner backfill invariant tests for FVV and FVCV-extension
type: implementation
---

## Issue #1600 — test(ci): add finder late-joiner backfill checks to FVV and FVCV-extension invariants

Added `test_fvv_finder_late_joiner_has_full_history` to FVV invariant file and
`test_fvcv_extension_finder_late_joiner_has_full_history` +
`test_fvcv_extension_coordinator_late_joiner_has_full_history` to the
FVCV-extension invariant file. All three tests use `check_late_joiner_has_full_history`
with `early_actor="vendor"` and skip automatically when devlogs are absent.

PR: <https://github.com/CERTCC/Vultron/pull/1647>
