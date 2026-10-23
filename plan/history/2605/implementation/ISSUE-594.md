---
source: ISSUE-594
timestamp: '2026-05-21T18:10:30.921129+00:00'
title: 'Fix outbound routing: participant triggers address Case Actor only'
type: implementation
---

## Issue #594 — Fix outbound routing: participant trigger use cases must address Case Actor only, not all participants

All post-case-creation participant-originated trigger use cases were using
`case_addressees()` to address outbound activities, delivering them directly
to ALL participants instead of routing exclusively through the Case Actor.
This violated the canonical communication model (PCR-08-001, PCR-08-002):
`participant → CaseActor → CaseLogEntry → broadcast → participants`.

### Changes

- Extracted `_resolve_case_manager_id(case, dl) -> str | None` as a shared
  helper in `vultron/core/use_cases/_helpers.py`. Resolves the actor ID of
  the `CVDRole.CASE_MANAGER` participant; includes null-check for orphaned
  participant references.
- Fixed `SvcAddNoteToCaseUseCase` (`triggers/note.py`)
- Fixed `SvcEngageCaseUseCase`, `SvcDeferCaseUseCase` (`triggers/case.py`)
- Fixed `SvcProposeEmbargoUseCase`, `SvcAcceptEmbargoUseCase`,
  `SvcTerminateEmbargoUseCase`, `SvcRejectEmbargoUseCase`,
  `SvcProposeEmbargoRevisionUseCase` (`triggers/embargo.py`)
- Refactored `SvcAddParticipantStatusUseCase` to use the shared helper
  instead of inline loop
- Updated `test_note_trigger.py` and `test_trignotify.py` with proper
  `CaseParticipant(case_roles=[CVDRole.CASE_MANAGER])` setup and
  assertions that `to == [case_actor_id]`

PR: [#616](https://github.com/CERTCC/Vultron/pull/616)
