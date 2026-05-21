---
source: CONCERN-593
timestamp: '2026-05-21T16:33:14.215677+00:00'
title: Case Actor outbound routing model
type: learning
---

## Concern #593 — Case Actor Outbound Routing Model

**Category**: Architecture / Protocol Correctness
**Severity**: High
**Affected areas**: `vultron/core/use_cases/triggers/note.py`,
`vultron/core/use_cases/triggers/embargo.py`,
`vultron/core/use_cases/triggers/case.py`

### Root Cause

Sender-side trigger use cases (`SvcAddNoteToCaseUseCase`, embargo triggers,
`SvcEngageCaseUseCase`, `SvcDeferCaseUseCase`) use `case_addressees()` to
address outbound activities. This function returns ALL participants in the case
excluding the caller, causing participant-originated messages to be delivered
directly to all peers rather than routing exclusively through the Case Actor.

This violates the canonical CVD communication model:

```text
participant → CaseActor → CaseLogEntry → Announce(CaseLogEntry) → participants
```

The only correct use of `case_addressees()` is on the Case Actor's outbound
fan-out side (broadcasting `Announce(CaseLogEntry)` to all participants).

### Impact

- Demo and protocol flows show incorrect peer-to-peer communication after case
  creation
- Case Actor is bypassed, so CaseLogEntry commits and Announce broadcasts do
  not occur for most protocol messages
- The `sync-log-entry` demo endpoint masks the problem by manually injecting
  entries as a workaround

### Fix Plan

Three implementation issues created:

- #594 (size:M): Fix outbound routing in all trigger use cases — replace
  `case_addressees()` with the Case Actor ID (CVDRole.CASE_MANAGER participant)
- #595 (size:M): Implement automatic CaseLogEntry + Announce broadcast cascade
  in all Case Actor received handlers — blocked by #594
- #596 (size:L): Refactor sender-side trigger use cases into Behavior Trees —
  blocked by #594

### Documentation

- Added PCR-08 requirement group to `specs/participant-case-replica.yaml`
  (6 requirements, PCR-08-001 through PCR-08-006)
- Created `notes/case-communication-model.md` with the canonical communication
  model, scope table, antipattern analysis, and known gaps
- Added `case_addressees()` antipattern pitfall entry to `AGENTS.md`

**Resolved**: 2025-07-14 — implementation tracked in #594, #595, #596.
Docs PR: <https://github.com/CERTCC/Vultron/pull/597>.
