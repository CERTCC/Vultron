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

## 2026-02-20: BT-2.0 — CM-04 + ID-04-004 Compliance Audit COMPLETE

**BT-2.0.1 & BT-2.0.2 (verification)**: Confirmed `engage_case` and
`defer_case` handlers correctly update `ParticipantStatus.rm_state` (via
`_find_and_update_participant_rm` in `nodes.py`) and do not touch `CaseStatus`.
No code change needed.

**BT-2.0.3 & BT-2.0.4 (idempotency guards)**: Added idempotency check to
`_find_and_update_participant_rm` helper in `vultron/behaviors/report/nodes.py`.
Before appending a new `ParticipantStatus`, the helper checks if the latest
entry already has the target RM state. If so, it logs at INFO and returns
SUCCESS without side effects, satisfying ID-04-004 MUST.

**BT-2.0.5 (tests)**: Added two new tests to
`test/behaviors/report/test_prioritize_tree.py`:
- `test_engage_case_tree_idempotent`: runs EngageCaseBT twice; verifies
  exactly one ACCEPTED entry and final state is ACCEPTED.
- `test_defer_case_tree_idempotent`: runs DeferCaseBT twice; verifies
  exactly one DEFERRED entry and final state is DEFERRED.

Total test count: 474 passed, 2 xfailed (was 472).

**Pattern for future BTs**: Use the same helper-level idempotency check rather
than adding a dedicated BT node. This avoids BT tree complexity while still
satisfying ID-04-004.

---

