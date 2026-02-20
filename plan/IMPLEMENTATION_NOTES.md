# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate 
insights, issues, and learnings during the implementation process.

Append new notes below this line.

---

## 2026-02-20: Spec Updates — New case-management.md and idempotency.md

Two specs were added/consolidated since the last plan revision:

**`specs/case-management.md`** (NEW):
- Formalizes requirements from `plan/PRIORITIES.md` (Priority 100, 200) and
  `notes/case-state-model.md` into testable specs.
- Key new requirement: **CM-04** mandates correct scoping of state updates:
  - RM state transitions → `ParticipantStatus.rm_state` (participant-specific)
  - EM state transitions → `CaseStatus.em_state` (shared per case)
  - PXA state transitions → `CaseStatus.pxa_state` (shared per case)
  - VFD state transitions → `ParticipantStatus.vfd_state` (participant-specific)
- Before implementing any state-changing handler, consult `notes/case-state-model.md`
  "Participant-Specific vs. Participant-Agnostic States" section.

**`specs/idempotency.md`** (CONSOLIDATED, now standalone):
- Previously scattered across inbox-endpoint.md, message-validation.md,
  handler-protocol.md. Now the authoritative source.
- **ID-04-004 is MUST**: state-changing handlers MUST be idempotent (not just SHOULD).
  This applies to any handler that transitions RM, EM, or CS state.
- Pattern: check current state before transitioning; if already in target state, log
  at INFO and return without side effects.

**Implication for BT implementations going forward**:
- Every BT node that transitions RM/EM/CS/VFD state MUST include a precondition
  node that checks whether the transition has already occurred (idempotency guard).
- The existing `validate_report` BT uses `CheckRMStateValid` as an early-exit
  idempotency check — use this pattern for all future state-machine BT nodes.


