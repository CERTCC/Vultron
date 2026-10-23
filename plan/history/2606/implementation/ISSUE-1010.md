---
source: ISSUE-1010
timestamp: '2026-06-16T19:41:12.575301+00:00'
title: Add failure-mode tests to test_defer.py (SvcDeferCaseUseCase)
type: implementation
---

## Issue #1010 — Add failure-mode tests to test_defer.py (SvcDeferCaseUseCase)

Added three failure-mode tests to `test/core/use_cases/triggers/case/test_defer.py`
covering the documented failure scenarios for `SvcDeferCaseUseCase`:

- `test_defer_case_actor_not_found_raises_error`: unknown actor_id raises
  `VultronNotFoundError` (exercised via `resolve_actor` in `_prepare()`).
- `test_defer_case_not_found_raises_error`: unknown case_id raises
  `VultronNotFoundError` (exercised via `resolve_case` in `_prepare()`).
- `test_defer_case_rm_not_updated_when_no_participant`: case has a valid
  vendor participant (RM transition succeeds) but no CASE_MANAGER participant,
  so `ResolveCaseManagerNode` fails → `VultronValidationError`.

The third test was revised after code review caught that a naive empty
`case_participants` fixture caused the RM transition node (not the
CASE_MANAGER resolver) to fail first — the corrected fixture stores a real
vendor participant with RM history so the correct BT node is exercised.

Also promoted `WireParticipantStatus` import from inline function scope to
module level.

PR: [#1015](https://github.com/CERTCC/Vultron/pull/1015)
