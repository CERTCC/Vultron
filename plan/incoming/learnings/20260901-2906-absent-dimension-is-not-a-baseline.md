---
title: "An absent VF/D dimension is absent, not at its initial state — and first observations are accepted"
type: learning
timestamp: "2026-09-01T00:00:00Z"
source: ISSUE-2906
signal: design-question
---

Two semantics decisions made while fixing #2906, both now stated in
`_adjudicate_vf`'s docstring and in RSH-05-020's `note:`, because both are easy
to get wrong from the code alone and each has already been misread once.

**1. `vf is None` means the participant has no vendor path, not `CS_vf.vf`.**

Under ADR-0075 the dimension's *presence* carries role information: VENDOR ⇒
`vf` non-None (auto-seeded by `ParticipantStatus._enforce_role_dimension_invariant`),
DEPLOYER ⇒ `d` non-None. So `None` is structural absence. Reading it as the
initial state would make a DEPLOYER-only participant's legitimate `d=D` violate
VF↔D ("deployed without ready") — a spurious refusal.
`violation_vf_d_entailment` documents this and a test already pins it.

**2. A first observation of a dimension is accepted when nothing contradicts it.**

`current is None` + non-None assertion is not an unchecked gap; there is no
prior value to regress from, so no monotonicity rule can apply. Liberal accept
(ISSUE-2229) says record it. What constrains it is the *cross-machine*
entailment pass, which needs no history: a ready fix still entails an accepted
report regardless of whether the receiver has seen this participant's VF before.

The general shape: **history-relative rules (monotonicity, adjacency,
regression) cannot constrain a first observation; only history-free rules
(entailments, role gates) can.** When a dimension can be absent, expect to need
one of each, and do not reach for a synthetic baseline to make the
history-relative rule apply — that fabricates history the receiver does not
have.

`_adjudicate_case_status` has the same absent-current shape for `pxa` and the
same answer, noted in its docstring.
