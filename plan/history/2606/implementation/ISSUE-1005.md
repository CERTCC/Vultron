---
source: ISSUE-1005
timestamp: '2026-06-16T18:37:41.433757+00:00'
title: Apply SvcBTTriggerBase to case trigger use cases
type: implementation
---

## Issue #1005 — Apply SvcBTTriggerBase to case trigger use cases

Applied the `SvcBTTriggerBase` ABC to all six case trigger use case classes
under `vultron/core/use_cases/triggers/case/`, removing duplicated `__init__`,
`BTBridge` construction, and failure guards from each class.

Key implementation decisions:

- Added `_extra_execute_kwargs()` hook to `SvcBTTriggerBase` (returns
  `dict[str, Any]`, default `{}`) so `SvcAddObjectToCaseUseCase` and
  `SvcAddReportToCaseUseCase` can pass `case_id` to the blackboard for
  `UpdateActorOutbox`.
- Removed the standalone `_execute_add_object_trigger_bt()` private function
  from `add_object.py`; both add-object classes now implement the BT hooks
  directly.
- `SvcAddParticipantStatusUseCase` overrides `execute()` to return
  `{activity_id, status_id}` (different shape from base class default).
- All 3422 existing tests pass unchanged.

PR: [#1009](https://github.com/CERTCC/Vultron/pull/1009)
