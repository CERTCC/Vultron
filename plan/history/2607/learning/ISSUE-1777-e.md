---
title: Revise a recent ADR in place rather than appending an amendment that contradicts it
type: learning
timestamp: "2026-07-31T00:30:00+00:00"
source: ISSUE-1777-e
signal: process-issue
---

ADR-0041 (accepted 2026-07-28) had three statements that its own step-3
implementation contradicted: Option 3 read as rejecting the
`("Add","CaseStatus")` authorization the chosen option actually requires; "What
is removed" listed the `Offer(CaseManagerRole)` accept path and
`CreateCaseActorNode` unqualified, conflicting with MUST-level DEMOMA-08 specs
and with `create_tree.py`; and the Issue #1767 consequence claimed back-fill
removal was sufficient alone (true only for multi-actor deployments).

My first instinct was a dated `### Amendment` section, following the precedent in
`ADR-0024`. The user redirected: an ADR states the decision chosen and what was
considered and rejected — not the meandering path to it. "Y was chosen" followed
by "but actually we did X" creates narrative entanglement and makes the current
expectation harder to read.

**Why:** The value of an ADR is that a future reader can see what is expected
*now* in one pass. An append-only trail forces them to reconcile the body against
its own addenda to work out which statement is live.

**How to apply:** When an ADR is contradicted by its own implementation, first
ask whether the *decision* changed or only its *description*. If the decision
still holds and the ADR is recent, revise the affected sections in place and add
a short `### Revision history` block at the end recording what was corrected and
why — enough for provenance, not a narrative. If the decision itself changed,
supersede and archive instead. Amendment sections suit genuinely *additive*
discoveries (ADR-0024's fifth node shape), not corrections. Recent authorship
strengthens the case for revision: little has been built on the wrong text yet.

**Promoted**: 2026-07-31 — captured in `docs/adr/index.md` (Revising vs. amending an ADR section).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1900>0>0>0>0>.
