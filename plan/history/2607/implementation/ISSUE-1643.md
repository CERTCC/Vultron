---
source: ISSUE-1643
timestamp: '2026-07-24T20:21:26.503593+00:00'
title: Add CVDRole.VENDOR precondition guard to fix-lifecycle milestone helpers
type: implementation
---

## Issue #1643 — fix: add CVDRole.VENDOR precondition guard to verify_fix_ready and verify_fix_deployed

Added `_assert_vendor_role` helper to `vultron/demo/helpers/milestones.py` that
fetches the participant for `receiver_actor_id` and asserts `CVDRole.VENDOR in
participant.case_roles` before proceeding with VFD state checks. Both
`verify_fix_ready` and `verify_fix_deployed` now call this guard first.

Added 8 unit tests in `test/demo/test_milestones_vendor_guard.py` covering
non-VENDOR raises (with actor ID and role info in message), valid VENDOR passes,
and missing-participant raises.

Implements DEMOMA-15-001. PR: <https://github.com/CERTCC/Vultron/pull/1701>
