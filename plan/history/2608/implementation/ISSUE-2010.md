---
source: ISSUE-2010
timestamp: '2026-08-06T00:13:41.703499+00:00'
title: 'Fix ledger idempotency guard rejections (issue #2010)'
type: implementation
---

## Issue #2010 — Fix ledger idempotency guard rejections: silent no-op + reusable guard node

Implemented CLP-13-001/CLP-13-002 compliance for BT idempotency guard nodes.

### What was done

- Created `vultron/core/behaviors/idempotency.py` with `SilentIdempotencyGuardMixin` (CLP-13-002): structural enforcement that guard no-ops never write a `CaseLedgerEntry`
- Fixed `CheckInviteeNotAlreadyParticipantNode` in `accept_invite_tree.py`: true-duplicate (backfill-complete) path now uses `_idempotent_failure` → FAILURE; backfill-incomplete resume path correctly returns SUCCESS
- Applied mixin to `CheckCaseStatusIdempotencyNode` in `status/nodes/case_status.py`
- Added 15 unit tests in `test/core/behaviors/case/nodes/test_idempotency_guards.py`
- Added `check_no_rejected_invite_entries` and `test_invariant_clp13_no_rejected_invite_entries` in CI invariants for fvcv_handoff

### PR

<https://github.com/CERTCC/Vultron/pull/2024>
