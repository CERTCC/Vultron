---
title: >-
  RSH-08-014 and PRM-06-003/004 permit an on-behalf status carrying both moves,
  but the only such status lands on VfD, which CSB-17-001 forbids
type: learning
timestamp: 2026-11-04T23:55:00Z
source: ISSUE-3046
signal: spec-contradiction
---

## Trigger

You are reading, or testing, the on-behalf status rules: RSH-08-014, or
PRM-06-003 and PRM-06-004. One of them says a CASE_MANAGER or Case Owner may
assert `v→V` for a Vendor-role participant, `d→D` for a Deployer-role
participant, "or both". You are about to write or trust a test for the "both"
case.

## The contradiction

The two on-behalf moves are fixed: `vf → Vf` and `d → D`
(`on_behalf_status_violations` in
`vultron/core/behaviors/status/nodes/status_subject.py` permits exactly those
pairs). A status carrying both therefore asserts `vf=Vf` **and** `d=D`, which
is the compound state `VfD` — a fix deployed before it was ready. CSB-17-001
names exactly four valid VFD states (`vfd`, `Vfd`, `VFd`, `VFD`), and `VfD` is
not one of them, so `composite_state_violations` refuses it on every path.

So the "or both" permission is unreachable end to end, for any target. A
DEPLOYER-only participant has no `vf` dimension, so "both" cannot apply to it;
a VENDOR+DEPLOYER participant lands on `VfD`. PRM-06-008 already requires the
entailments to be applied to an on-behalf `d→D`, which is what refuses it — so
the refusal is correct behaviour, not a defect. What is wrong is a MAY nobody
can exercise.

## Why it matters

Only the shape rule's own unit test covers the "both" case
(`test_both_moves_together_are_one_on_behalf_assertion` in
`test/core/behaviors/status/nodes/test_status_subject.py`), and it has to build
an impossible fixture to do it. Before #3046 that test read as "both moves
together are accepted", which is not what happens; it now asserts the
impossibility as well, so the two layers are both stated. The received-side
end-to-end tests in `test/core/use_cases/received/test_status.py` cover `v→V`
alone and `d→D` alone — the admitted `d→D` case uses a DEPLOYER-only target,
where the VF↔D rule cannot apply — and none covers "both", because none can.

The risk is the next reader treating the refusal as the bug and "fixing" it,
which would mean making `VfD` representable.

## What is undecided

Whether to narrow RSH-08-014 and PRM-06-003/004 so they stop granting a
permission the entailments always refuse, or to keep "or both" and record in
the spec that it is a statement about the shape rule only. Narrowing changes
what the requirements oblige, so it needs the user's decision, not an agent's.
It was raised as a question on the #3046 run rather than filed as a Concern.
