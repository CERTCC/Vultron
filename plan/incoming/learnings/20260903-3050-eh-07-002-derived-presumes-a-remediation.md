---
title: "EH-07-002's root/derived rule silently presumes which remediation a caller will attempt"
type: learning
timestamp: "2026-09-03T00:00:00Z"
source: ISSUE-3050
signal: spec-ambiguity
---

EH-07-002 defines the classification purely structurally:

> A rule reading a single dimension is always root. A rule reading more than one
> dimension is derived when any dimension it reads already carries a
> single-dimension violation, and root otherwise.

"Derived" only earns its name if fixing the root clears it. But whether it does
depends on **what the caller is expected to do about the root** — and the spec
never says. Two single-dimension rules behave differently:

- **A transition fault** (`vf → VF` skips `Vf`) is remedied by asserting a legal
  value. The multi-dimension entailment that read the illegal value goes away.
  Derived is correct.
- **A role gate** (asserting `d` without DEPLOYER) has two conceivable
  remedies. *Withdraw the claim* → the entailment reading `d` goes away, so
  derived is correct. *Acquire the role* → the entailment survives and resurfaces
  as root on the next submission, which is the fix-one-resubmit loop EH-07-001
  exists to prevent.

The domain settles it: a participant does not hold a dimension it has no role
for at all — a non-DEPLOYER's `d` is **absent**, not at an initial value
(ADR-0075) — and an actor cannot grant itself a role. So "withdraw the claim" is
the only real remediation and the structural rule gives the right answer. But
that reasoning lives entirely outside the spec, in ADR-0075 and the role model.

**Why this is worth recording:** a reviewer reading EH-07-002 in isolation
reached the opposite conclusion, constructed a repro that put a participant on a
dimension it had no role for, and reported a MEDIUM defect. The repro state
cannot arise, so the finding dissolved — but only after checking the state
against the role model. The next implementer extending the rule set will be in
the same position, and the spec as written invites the same wrong turn: it reads
as a pure graph property when it actually rests on a domain premise about
remediation.

**Suggested spec amendment:** EH-07-002 should state the premise it depends on —
that a violation is derived when the *expected remediation* for the overlapping
single-dimension violation also clears it, and that for a role gate the expected
remediation is withdrawing the assertion rather than acquiring the role. Without
that sentence the requirement is under-determined for any rule family added
later whose remediation is not "assert a different value".

Pinned by `test_never_combination_is_root_for_a_role_holder` and
`test_role_gate_derives_its_entailments` in
`test/core/states/test_participant_transitions.py`, which encode both halves so
the semantics cannot be "corrected" back.
