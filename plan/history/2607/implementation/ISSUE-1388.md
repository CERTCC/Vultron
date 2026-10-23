---
source: ISSUE-1388
timestamp: '2026-07-15T15:32:34.056156+00:00'
title: 'refactor: replace getattr case_roles reads with .roles property in core'
type: implementation
---

## Issue #1388 — refactor: replace direct case_roles getattr() reads with .roles property in core (PRM-01-003)

Replaced all 8 `getattr(x, "case_roles", [])` call sites in `vultron/core/` with `.roles` property access or `is_participant_model()` guards per PRM-01-003. Added architecture ratchet test `test_no_getattr_case_roles_read_in_core()` to prevent regression.

Key decisions:

- `common.py` uses `getattr(existing, "roles", [])` not `existing.roles` because `existing` is typed `Any` and the `is not None` narrowing causes pyright error at `dl.save(existing)` downstream
- `case_manager_role.py` extracted `_find_reporter_id` helper to reduce complexity under C901 gate; the helper includes `case_participants` fallback (matching `_resolve_case_manager_id` pattern) so bootstrap trust is not skipped when `actor_participant_index` is unpopulated
- `status.py`: consistent `is_participant_model()` guard for both `participant_roles` and `raw_consent` extraction

PR: <https://github.com/CERTCC/Vultron/pull/1443>
4740 unit tests pass; black/flake8/mypy/pyright clean.
