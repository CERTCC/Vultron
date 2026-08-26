---
title: A guard record written before its transition converts "not yet" into "never"
type: learning
timestamp: 2026-08-25
source: ISSUE-2548
signal: concern
---

`TransitionRMtoValid` had two halves: write the report-phase `RM.VALID`
`ParticipantStatus`, and advance the case-scoped `CaseParticipant`. It did them in
that order. When the case was absent the second half was skipped — and the node
returned SUCCESS, because the first half had succeeded.

The damage is not the missed update. It is that `CheckRMStateValid` reads *that
same record* to decide whether the transition still needs doing. So the first
failed attempt wrote its own permanent alibi: every later `validate-report`
short-circuited to SUCCESS, `ValidationActions` could never be re-entered, and
the participant stayed at `RM.RECEIVED` for the life of the case. A twenty-second
demo gate timeout and an M4/M5/M6 cascade, all from a write ordering.

What makes this class hard to see: nothing raises, nothing logs an error, and the
node's own unit test passes — the record it was asked to write got written. The
failure is only visible from *outside* the node, in the second tick.

**Why this is filed as a concern and not just a fix.** The same shape is
reachable anywhere a record does double duty as state and as idempotency
evidence, which in this codebase is common: `_idempotent_create` exists precisely
to make writes re-runnable, and the deterministic ID scheme
(`_report_phase_status_id`) means the guard and the write agree by construction.
That is a good design; it just makes ordering load-bearing in a way no type
signature shows. `ID-04-005` now states the rule, but the rule has no ratchet
behind it.

**How to apply.**

- In any multi-half transition, identify which write a later guard reads. That
  write goes **last**. If two writes both feed guards, the transition wants a
  single commit point, not an ordering convention.
- The test that catches it cannot live inside the node. It has to drive the
  transition under the failing precondition and then assert the *retry* still
  works — see `test_full_flow_no_rm_valid_before_case_replica_arrives`.
- A green scenario is not evidence of correctness here. On HEAD before the fix,
  `fv` passed and `fcvcv`/`fcv-reject`/`fvcv-handoff` failed, and `fv` calls the
  identical helper. It was winning a race, not behaving differently — see
  [[tests-that-pass-while-being-wrong]].
- Related: [[co-location-is-not-visibility]] supplied the failing precondition
  that exposed this.
