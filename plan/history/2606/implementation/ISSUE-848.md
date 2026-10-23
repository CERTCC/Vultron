---
source: ISSUE-848
timestamp: '2026-06-09T20:49:21.724996+00:00'
title: Migrate SvcProposeEmbargoRevisionUseCase to BTBridge pattern
type: implementation
---

## Issue #848 — Migrate SvcProposeEmbargoRevisionUseCase to BTBridge pattern

Migrated `SvcProposeEmbargoRevisionUseCase` from inline `EmbargoLifecycle` +
`send_case_actor_activity` calls to the BTBridge pattern, fixing BT-15-001
and BT-15-002 violations and bringing the use case into parity with all other
embargo trigger use cases.

**Changes:**

- Added `ValidateEmbargoRevisionStateNode` to `trigger_nodes.py` — guards
  that case EM state is ACTIVE or REVISE before a revision proposal proceeds;
  captures domain error in `result_out` for clean re-raise
- Added `propose_embargo_revision_trigger_bt()` factory to `trigger_tree.py`
  — sequences the state guard, `ProposeEmbargoLifecycleNode`,
  `PersistEmbargoEventNode`, and `sender_side_bt`
- Refactored `SvcProposeEmbargoRevisionUseCase.execute()` to use BTBridge;
  removed inline `EmbargoLifecycle`, `TransitionMode`, `EM`, and
  `send_case_actor_activity`
- Added 12 new tests: 7 for `ValidateEmbargoRevisionStateNode`
  (SUCCESS/FAILURE per EM state, error type assertion, missing case) and 5
  for the migrated use case (ACTIVE→REVISE, REVISE→REVISE counter-revision,
  outbox enqueued, invalid state raises, invalid state does not persist)

**Verification:** 3091 passed, 11 skipped; Black, flake8, mypy, pyright clean.

PR: [#854](https://github.com/CERTCC/Vultron/pull/854)
