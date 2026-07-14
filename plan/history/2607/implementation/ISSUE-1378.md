---
source: ISSUE-1378
timestamp: '2026-07-14T16:52:18.786308+00:00'
title: consolidate duplicate _as_id() and case-manager helper copies
type: implementation
---

## Issue #1378 — refactor: consolidate duplicate _as_id() and case-manager helper copies

Removed three duplicate case-manager lookup variants and two extra _as_id() copies. Unified into _resolve_case_manager_id (use_cases/_helpers.py) covering both the fast actor_participant_index path and the bootstrap case_participants fallback. Deleted broadcast.py entirely. 4643 tests pass. PR: <https://github.com/CERTCC/Vultron/pull/1413>
