---
source: CONCERN-4479
timestamp: '2026-10-12T15:46:20.065400+00:00'
title: ADR-0120's 72-hour free-edit window is too short to revise a new ADR; timers
  alone are the wrong signal
type: learning
---

## Summary

ADR-0120 gives a new or materially edited ADR only 72 hours of free in-place
editing before it becomes `accepted-provisional`, and only to day 10 before it
becomes `accepted`. That is not enough time to revise a new ADR; after 72 hours
every material edit needs the human edit-or-supersede ask.

## Surface Symptom vs. Underlying Problem

**Surface:** 72 hours is too short; make the number bigger.

**Underlying:** the timers do two jobs at once: they give a fresh decision
room to settle, and they guarantee nothing stays undecided forever (an ADR
stuck in `proposed` that nobody treats as decided). A short wall-clock timer
serves the second job well but starves the first: elapsed time runs out over
weekends, or while an agent-written ADR sits unread, whether or not anyone is
revising it. Elapsed time alone is the wrong signal for "this has had its
chance to be revised".

**Keep as is:** the three epochs, the guarantee that every ADR eventually
hardens (the timers remain as a backstop), epochs measured from `updated` (not
`created`), the early-hardening escape when a dependent implementation merges,
the human `status_override`, and the edit tiers.

## Category

- [ ] Top risk
- [ ] Technical debt
- [ ] Security
- [ ] Performance / scaling
- [ ] Fragile / high-churn area
- [x] Other — process / governance tooling

## Severity

medium

## Evidence

- `docs/adr/0120-adr-lifecycle-epochs-and-edit-tiers.md` — epoch table:
  under 72 hours `proposed`, 72 hours to day 10 `accepted-provisional`,
  day 10 on `accepted`
- `specs/meta-specifications.yaml` MS-14-007 — states the same boundaries
- `vultron/metadata/adr/lifecycle.py` — `EPOCH_2_START_DAYS = 3`,
  `EPOCH_3_START_DAYS = 10`
- ADR-0120 itself (created 2026-10-06) is already `accepted-provisional`, so
  changing the timing is itself an epoch-2 edit of ADR-0120

## Impact if Ignored

Authors either rush revisions into the first 72 hours or hit the
ask/supersede step on decisions that have not actually settled — the
dead-record churn ADR-0120 was written to prevent. The fixed clock also
penalizes ADRs written when no human is around to read them.

## Suggested Action

1. **Lengthen the timers, keep them as backstops.** Starting proposal (to be
   settled in planning): `accepted-provisional` 14 days after `updated`, and
   `accepted` 14 days after that (day 28 from `updated`). A material edit
   bumps `updated` and restarts the clock, as today.
2. **Let events advance an ADR ahead of its timer.** Primarily a human marking
   the ADR reviewed/ratified, which ends epoch 1 early; keep the existing
   early hardening when a dependent implementation merges. The longer timers
   then guarantee nothing gets stuck, while events keep settled decisions
   from waiting out the clock.
3. **Update the governing artifacts together:** ADR-0120 (edit in place vs.
   supersede is the human's epoch-2 call, made in planning), MS-14-007,
   `lifecycle.py` constants and the epoch lint/drift workflows, and
   `notes/specs-vs-adrs.md`.

**Resolved**: 2026-10-12 — implementation tracked in #4501.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4500>.

Spec: `specs/meta-specifications.yaml`.
