---
title: A state-transition log line belongs at the narrowest writer that knows the before-state
type: learning
timestamp: 2026-08-05
source: ISSUE-1988
signal: design-question
---

`notes/structured-logging.md` said to add narrative INFO lines "in the BT leaf
node that performs the state write". That rule is necessary but not sufficient:
the leaf node often knows only the *target* state, so following it literally
produces lines that are wrong rather than merely incomplete.

Three concrete failures from ISSUE-1988, all caught only after the first
implementation was already passing its own tests:

- **`TransitionCStoFixReady` / `TransitionCStoFixDeployed` are the wrong home.**
  Each knows it is writing `VFd` / `VFD`, but not the origin — their
  pre-existing messages literally read `VFD → VFd` and `VFD → VFD`. The
  before-state lives in `CreateParticipantStatusNode`, which they delegate to.
  The narrative line went there; the leaf nodes kept DEBUG detail lines.

- **A "single write path" claim must be verified, not assumed.**
  `update_participant_rm_state()` was documented as *the* per-participant RM
  writer. `CreateParticipantStatusNode` also appends a `ParticipantStatus` with
  an explicit `rm_state` without going through it — so the leave-case
  RM → CLOSED transitions produced no RM line and AC-12 was unmet while the
  notes asserted it was met. Grep for every writer of the field, not just the
  obvious helper.

- **The before-state source must be the same store the write lands in.**
  `CreateParticipantStatusNode` records PXA on the *participant* snapshot and
  never appends to `case.case_statuses`, so reading `case.current_status.pxa`
  reported a stale value forever and every repeat write re-announced the
  public-disclosure milestone. Reading the participant's own latest
  `case_status.pxa` fixed it.

**Two invariants worth applying to any future transition-logging work:**

1. **Guard the no-op.** If `before == after`, emit nothing. Re-asserting a
   state is bookkeeping, and a line reading `RM ACCEPTED → ACCEPTED` or
   `CS: pxa → Pxa` on the second call actively misinforms. Read the after-state
   back from storage rather than hardcoding the intended target, since BTs can
   succeed via idempotent paths.
2. **Guard the monotonicity violation.** CS/RM/EM events are forward-only, so a
   backward move is an anomaly, not a milestone — log it at WARNING with a
   distinct label. Deriving an event name by diffing sub-dimensions silently
   yields "no change" for a regression, producing a line that claims a
   transition and denies it in the same breath.

A no-op or backward-transition test is the cheapest way to catch all of this:
run the same write twice and assert the second emits nothing.

**Promoted**: 2026-08-17 — captured in notes/structured-logging.md (No-op and monotonicity guards section).
Docs PR: TBD.
