---
source: ISSUE-849
timestamp: '2026-06-10T14:11:36.847172+00:00'
title: Migrate SvcInvalidateReportUseCase, SvcRejectReportUseCase, SvcCloseReportUseCase
  to BTBridge
type: implementation
---

## Issue #849 — Migrate SvcInvalidateReportUseCase, SvcRejectReportUseCase, SvcCloseReportUseCase to BTBridge

Replaced inline `ParticipantStatus` creation and procedural state transitions
in three report-lifecycle trigger use cases with proper BT factory functions
and `BTBridge.execute_with_setup()` calls. Satisfies BT-15-001 and BT-15-002.

### New BT nodes (`vultron/core/behaviors/report/nodes/`)

- `TransitionRMtoClosed` — persists report-phase `ParticipantStatus(rm_state=RM.CLOSED)`
- `CheckReportNotClosed` — duplicate-close guard; writes
  `VultronInvalidStateTransitionError` into `result_out["error"]` on FAILURE
- `EmitInvalidateReportActivity` — creates and queues `TentativeReject(Offer)`
- `EmitCloseReportActivity` — creates and queues `Reject(Offer)` (shared by
  reject/close paths)

### New BT factories (`vultron/core/behaviors/report/trigger_report_trees.py`)

- `create_invalidate_report_trigger_tree` — Emit → TransitionRMtoInvalid
- `create_reject_report_trigger_tree` — Emit → TransitionRMtoClosed (no guard)
- `create_close_report_trigger_tree` — CheckNotClosed → Emit → TransitionRMtoClosed

### Bug fixed during implementation

`py_trees.common.Status.SUCCESS.value` is `'SUCCESS'` (uppercase), not
`"success"`. Three use cases had fragile `result.status.value != "success"`
comparisons that always evaluated True regardless of BT outcome. Fixed by
importing `Status` and comparing `result.status != Status.SUCCESS`.

### Outcome

3113 tests passing, all linters clean (Black, flake8, mypy, pyright).

PR: [#858](https://github.com/CERTCC/Vultron/pull/858)
