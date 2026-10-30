---
title: "A selector that reads only its own eligibility predicates silently overrides authorities the project established elsewhere"
type: learning
timestamp: "2026-09-21T20:30:00Z"
source: ISSUE-3482
signal: theme-candidate
---

**Trigger.** You are reading or writing a candidate selector — work selection,
routing, eviction, retry eligibility — whose policy is a list of filter
predicates.

**Claim.** A predicate list looks complete: each clause is individually
defensible and there is no empty slot to notice. So authorities the project
already established elsewhere for the same decision (a spec-named field, a
sibling skill's routing table) are silently left out, and often fail without a
visible symptom. The cheap check is structural: **a selector cannot apply a
signal its query does not request**, so the query's field list is an upper bound
on the policy it can implement.

**Evidence.** `propose-bundle` filtered on open/unassigned/unblocked/leaf and then
took the first five in GitHub order, so it bundled an `Idea`, a `Someday`
`Concern`, and a `Bug` together. The rules it missed were all already in force:
`issueType` routing (`work-issue`), `Schedule` as the priority authority
(PAD-03-001), and `size:` labels (PAD-05). Its shared query
(`query-epic-subissues.sh`) fetched `labels` but neither `issueType` nor
`Schedule`; the `build` sibling shared the query and the defect.

**How to apply.**

1. Compare what the selector *fetches* against the decision's authorities.
   Anything absent from the query is a rule it cannot be applying, whatever its
   prose claims.
2. For each authority the project states elsewhere for this decision, find the
   line where the selector consumes it. A missing one is the finding.
3. Distrust a parenthetical asserting an ordering or priority ("query order
   reflects project priority"). That is where folk knowledge stands in for a
   named authority.

**What would confirm it.** A second, independent selector (not `build`, which
shares the query) found ignoring a spec-named authority already in force for its
decision. Mirror image:
[[20260916-3192-tightening-a-resolver-wakes-dormant-checks]], where a guard that
existed never ran.

**Unreproduced**: 2026-10-30 — single-witness theme-candidate older than 30 days with no
independent corroboration (BW-07-007). Archived without promotion.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5581>.
