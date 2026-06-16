---
source: ISSUE-1006
timestamp: '2026-06-16T18:31:53.203668+00:00'
title: Apply SvcBTTriggerBase to all remaining trigger use cases
type: implementation
---

## Issue #1006 — Apply SvcBTTriggerBase to all remaining trigger use cases

Completed full migration of all trigger use cases to the `SvcBTTriggerBase`
ABC introduced in #1004. Built missing BT implementations where needed so
no use case was excluded.

### Changes

- `_base.py` — Added `_requires_trigger_activity: bool = True` class
  variable; use cases that run BT-only workflows set it to `False` to
  bypass the `TriggerActivityPort` guard while still executing via
  `BTBridge`.
- `report/nodes/emit.py` — Added `EmitSubmitReportActivity` BT node.
- `report/trigger_report_trees.py` — Added `submit_report_trigger_bt`.
- `case/actor_trigger_trees.py` (new) — Added
  `EmitInviteActorToCaseNode`, `EmitAcceptCaseInviteNode`,
  `invite_actor_to_case_trigger_bt`, `accept_case_invite_trigger_bt`,
  `suggest_actor_to_case_trigger_bt`.
- `report.py` — Migrated `SvcValidateReportUseCase`
  (`_requires_trigger_activity = False`) and `SvcSubmitReportUseCase`
  (overrides `execute()` to return `{"offer": ...}`).
- `actor.py` — Fully migrated all three use cases:
  `SvcSuggestActorToCaseUseCase` (sender_side_bt / PCR-08-001),
  `SvcInviteActorToCaseUseCase` (Case Actor identity routing per
  PCR-08-007), `SvcAcceptCaseInviteUseCase` (validates invite type
  before running BT).
- `note.py` — Already migrated (no new changes).
- `sync.py` — Module-level comment added; standalone functions have no
  class migration needed.

### Outcome

3422 tests passed; mypy and pyright both clean (0 errors).

PR: [#1008](https://github.com/CERTCC/Vultron/pull/1008)
