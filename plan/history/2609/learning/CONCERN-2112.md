---
source: CONCERN-2112
timestamp: '2026-09-02T17:02:10.913493+00:00'
title: Atomic rejection does not license first-error-only diagnostics
type: learning
---

## Original concern

`CreateParticipantStatusNode._validate_transitions()` checked RM, then VFD, then
PXA in sequence and returned on the first invalid dimension. When two dimensions
were simultaneously invalid, only the first error was reported; the second was
silently dropped. No test covered the multi-dimension-invalid path.

The issue offered two resolution options and recommended option 1: keep
fail-fast, document the intent, and pin it with a test.

## What planning changed

**Direction reversed.** On maintainer direction, the intent is to collect every
recognizable error *while still* rejecting the update as a group — so a caller
does not have to play "bring me a rock". That is closer to the issue's option 2,
plus an explicit atomicity guarantee the issue did not state. Recorded as
EH-07-001.

**The code had moved.** `_validate_transitions()` no longer existed. It is now
`ValidateTriggerTransitionsNode.update()` in
`vultron/core/behaviors/case/nodes/participant/trigger_validation.py`, with six
sequential checks rather than three.

**Atomicity was already correct; only the diagnostics were wrong.** The trigger
path already rejected as a unit. The defect was the recorded *reasoning*:
`_validate_entailments`' docstring asserted "Emitting is all-or-nothing, so the
first violation is enough to refuse the whole trigger," and
`cross_machine_violations()` justified its ordering so that "a caller that
reports only the first violation reports the same one it always did." Atomicity
governs what is written; diagnostic completeness governs what is reported. The
two are independent, and the codebase had inferred one from the other twice.

**The root cause was a duplication, not a missing loop.**
`ValidateTriggerTransitionsNode` and `CreateParticipantStatusNode` each
implemented the VF, D and PXA transition checks and the VENDOR/DEPLOYER role
gates independently, with byte-identical message text — an ARCH-15-004 violation
— while each enforced a subset the other did not (only the guard evaluated the
cross-machine entailments; only the write node evaluated the compound CS
transition). Aggregating either node in isolation would have reported different
things depending on which path reached it. This is why the implementation issue
is `size:L`.

**The write node's apparent duplication is load-bearing.**
`CreateParticipantStatusNode` is reached from `develop_fix.py`, `deploy_fix.py`,
`close_case_effect.py` and two sites in `leave.py` without passing through the
trigger guard. For those five paths its checks are the only validation — exactly
BTND-10-001's stated rationale. It must keep them (BTND-10-003). It cannot
double-report on the trigger path, because the guard fails first and the
`memory=False` Sequence aborts before the write node ticks.

**The emit/receive asymmetry is Postel's maxim.** The trigger path fails closed
(conservative in what you send); the receive path per-dimension partial-accepts
(liberal in what you accept, ADR-0061, RSH-05-001/002). Nothing had recorded
that the two dispositions are two halves of one principle, so each reads as an
inconsistency from the other's side. ADR-0084 states it, which is what makes the
receive-path question answerable rather than perpetually reopened.

## Decisions recorded

- Reject the batch, report every violation (EH-07-001).
- Classify violations root vs. derived by **dimension overlap**: a
  single-dimension rule is always root; a multi-dimension rule is derived iff any
  dimension it reads already carries a single-dimension violation (EH-07-002).
  Chosen over a rule-to-rule dependency graph so a newly added rule is classified
  correctly by construction and the labelling cannot go stale.
- Carry violations structurally on the exception, following `DemoFailureError`'s
  shape, and add a `details` array to the HTTP error body (EH-07-003, EH-05-002)
  — the issue noted that callers parsing the message string break silently when
  internal check order changes.
- Compose the rule set once; both nodes call it and neither calls the individual
  predicates (BTND-10-002), per the ISSUE-2906 lesson that sharing predicates is
  not enough.
- `kind: architecture`, not `protocol`, for the BTND entries: they constrain the
  validators and the diagnostics never cross the wire.
- Aggregation stays within one node per path, so BT-13-001's first-failing-leaf
  contract needs no amendment and the tree is not restructured.

## Outcome

**Resolved**: 2026-09-02 — implementation tracked in #3050.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3049>.
ADR: `docs/adr/0084-report-every-violation-reject-the-batch.md`.
Specs: `specs/error-handling.yaml` EH-05-002 and EH-07-001..003;
`specs/behavior-tree-node-design.yaml` BTND-10-002, BTND-10-003.
Notes: `notes/domain-validation.md`, `notes/bt-pitfalls.md`.
Deliberately scoped out: #3040 — whether the receive path should also reject a
batch outright.
