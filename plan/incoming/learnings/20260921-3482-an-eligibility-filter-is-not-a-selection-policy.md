---
title: "A selector that reads only its own eligibility predicates silently overrides authorities the project established elsewhere"
type: learning
timestamp: "2026-09-21T20:30:00Z"
source: ISSUE-3482
signal: theme-candidate
---

`propose-bundle` selected work with a five-clause filter: open, unassigned, no
`stale-claim`, blockers closed, leaf. Every clause is correct, and the skill was
written as if the list were the whole selection policy — "take the first 5 in
GitHub order" once they pass.

The filter answers *can this issue be worked at all*. It does not answer *does
this issue belong with these four*, and nothing in the skill noticed the second
question was missing. The result was a proposed bundle containing an `Idea` (no
skill implements one), a `Someday` `Concern` (a human had already deprioritised
it), and a `Bug` routed to a different skill — all four indistinguishable,
because all four passed the filter.

What makes this worth remembering is **where the missing rules already lived**.
They were not undiscovered requirements; each was an authority the project had
already established, in force elsewhere, for exactly this decision:

- `issueType` → `work-issue`'s routing table, which the *same repo* applies when
  a single issue is handed to it.
- The `Schedule` field → PAD-03-001, a MUST naming it "the authoritative source
  for work priority ordering". The skill instead asserted that sub-issue list
  order "reflects project priority". It does not: that order is manual
  drag-order. A confident parenthetical was standing in for the authority.
- `size:` labels → PAD-05, present on 91% of open Tasks.

So the defect is not "we forgot to think about size". It is that a filter
predicate list *looks* complete — each clause is individually defensible and
there is no empty slot to notice — so the authorities that were never wired in
leave no trace of their absence. And two of the three failed **silently**: an
unread `Schedule` degrades ordering back to list order with nothing to observe,
whereas an unread `issueType` at least produced visibly wrong members.

There was a structural tell, and it is the cheap check: the shared query
(`query-epic-subissues.sh`) fetched `labels` but neither `issueType` nor
`Schedule`. **A selector cannot apply a signal its query does not request**, so
the query's field list is an upper bound on the policy the selector can possibly
implement — and comparing that field list against the project's stated
authorities is faster than auditing the selection prose. The sibling consumer
(`build`) shared the query and therefore shared the defect, which the field-list
check would also have found.

**How to apply.** When reading or writing any candidate selector — work
selection, routing, eviction, retry eligibility — do not audit the predicate
list for correctness; each predicate will look fine. Instead ask two questions:

1. What does the selector *fetch*? Anything absent from the query is a rule the
   selector cannot be applying, whatever its prose claims.
2. For the decision being made, which authorities does the project already
   state elsewhere — specs, a sibling skill's routing table, a board field? For
   each, find the line where this selector consumes it. A missing one is the
   finding.

Be suspicious of a parenthetical that asserts an ordering or priority
("ordering from the query reflects project priority"). Priority claims are the
ones most likely to be folk knowledge standing where a named authority belongs.

Corroboration needed: one instance so far (bundle selection, plus its `build`
sibling — the same selector shape, so not an independent witness). A second
witness would be any session that finds a filter/selection path ignoring a
spec-named authority that was already in force for that decision. The nearest
related claim in the queue is
[[20260916-3192-tightening-a-resolver-wakes-dormant-checks]], which is the
mirror image: there a *guard that existed* had never run because a resolver kept
returning `None`; here a guard *that should exist* was never written because the
predicate list looked finished.
