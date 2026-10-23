---
source: CONCERN-622
timestamp: '2026-06-09T17:22:55.060873+00:00'
title: Trigger-side execute() must delegate SM transitions to BTBridge
type: learning
---

## Concern #622 — Trigger-side execute() methods contain inline state machine logic that should live in Behavior Tree nodes

**Category**: Technical debt
**Severity**: Medium

### Summary

Trigger-side use-case `execute()` methods in `triggers/embargo.py`,
`triggers/case.py` (now `triggers/case/`), and `triggers/report.py`
contained substantial EM/RM state machine logic (state validation,
transition, cascade, and persistence) instead of delegating to Behavior
Trees via the BTBridge pattern. The existing guidance in
`notes/bt-integration.md` — "use procedural code for simple CRUD" — had
been used to justify this, but state machine transitions are not simple
CRUD, and that guidance has now been fully retired.

### Evidence

- `vultron/core/use_cases/triggers/embargo.py` — `SvcProposeEmbargoRevisionUseCase` calls `EmbargoLifecycle.propose_embargo()` and `send_case_actor_activity()` directly without BTBridge
- `vultron/core/use_cases/triggers/report.py` — `SvcInvalidateReportUseCase`, `SvcRejectReportUseCase`, `SvcCloseReportUseCase` create `ParticipantStatus` records with explicit `rm_state` fields outside any BT context
- `vultron/core/behaviors/bridge.py` — `BTBridge` + `execute_with_setup()` already exist and are used correctly on the `received/` side
- Four of five `triggers/embargo.py` `execute()` methods had already been migrated to BTBridge before this concern was planned

### Impact if Ignored

State machine transitions that bypass BTs cannot be audited, logged by
node, or observed at the BT level. Failure reasons are opaque (bare
raises rather than structured BT FAILURE status with
`get_failure_reason()`). The inconsistency between `received/`
(BT-delegating) and `triggers/` (procedural) makes the codebase harder
to reason about and extends, and undermines the core design goal of
having all business logic implemented in auditable behavior trees.

### Resolution

**Resolved**: 2026-06-09 — implementation tracked in #848, #849, #850.

Docs PR: [#847](https://github.com/CERTCC/Vultron/pull/847).
Spec: `specs/behavior-tree-integration.yaml` BT-15-001, BT-15-002.
Notes: `notes/bt-integration.md` § Trigger/Received Parity.
